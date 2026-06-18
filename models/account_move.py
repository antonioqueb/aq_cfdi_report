# -*- coding: utf-8 -*-
import base64
import io
import logging

from lxml import etree

from odoo import models

_logger = logging.getLogger(__name__)

try:
    import qrcode
    import qrcode.constants
except ImportError:
    qrcode = None

CFDI_NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
}
SAT_URL = "https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx"

IMP_NAMES = {"001": "ISR", "002": "IVA", "003": "IEPS"}

REGIMEN = {
    "601": "General de Ley Personas Morales",
    "603": "Personas Morales con Fines no Lucrativos",
    "605": "Sueldos y Salarios e Ingresos Asimilados a Salarios",
    "606": "Arrendamiento",
    "607": "Régimen de Enajenación o Adquisición de Bienes",
    "608": "Demás ingresos",
    "610": "Residentes en el Extranjero sin Establecimiento Permanente en México",
    "611": "Ingresos por Dividendos (socios y accionistas)",
    "612": "Personas Físicas con Actividades Empresariales y Profesionales",
    "614": "Ingresos por intereses",
    "615": "Régimen de los ingresos por obtención de premios",
    "616": "Sin obligaciones fiscales",
    "620": "Sociedades Cooperativas de Producción que difieren ingresos",
    "621": "Incorporación Fiscal",
    "622": "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras",
    "623": "Opcional para Grupos de Sociedades",
    "624": "Coordinados",
    "625": "Actividades Empresariales con ingresos a través de Plataformas Tecnológicas",
    "626": "Régimen Simplificado de Confianza",
}

USO_CFDI = {
    "G01": "Adquisición de mercancías",
    "G02": "Devoluciones, descuentos o bonificaciones",
    "G03": "Gastos en general",
    "I01": "Construcciones",
    "I02": "Mobiliario y equipo de oficina por inversiones",
    "I03": "Equipo de transporte",
    "I04": "Equipo de cómputo y accesorios",
    "I05": "Dados, troqueles, moldes, matrices y herramental",
    "I06": "Comunicaciones telefónicas",
    "I07": "Comunicaciones satelitales",
    "I08": "Otra maquinaria y equipo",
    "D01": "Honorarios médicos, dentales y gastos hospitalarios",
    "D02": "Gastos médicos por incapacidad o discapacidad",
    "D03": "Gastos funerales",
    "D04": "Donativos",
    "D05": "Intereses reales por créditos hipotecarios",
    "D06": "Aportaciones voluntarias al SAR",
    "D07": "Primas por seguros de gastos médicos",
    "D08": "Gastos de transportación escolar obligatoria",
    "D09": "Depósitos en cuentas para el ahorro",
    "D10": "Pagos por servicios educativos (colegiaturas)",
    "S01": "Sin efectos fiscales",
    "CP01": "Pagos",
    "CN01": "Nómina",
}

TIPO_COMPROBANTE = {
    "I": "Ingreso", "E": "Egreso", "T": "Traslado", "N": "Nómina", "P": "Pago",
}


class AccountMove(models.Model):
    _inherit = "account.move"

    # ------------------------------------------------------------------
    # Lectura del XML timbrado
    # ------------------------------------------------------------------
    def _aq_get_cfdi_xml(self):
        self.ensure_one()
        Att = self.env["ir.attachment"]
        domain = [("res_model", "=", "account.move"), ("res_id", "=", self.id)]
        atts = Att.search(domain + [("mimetype", "in", ["application/xml", "text/xml"])], order="id desc")
        if not atts:
            atts = Att.search(domain + [("name", "ilike", ".xml")], order="id desc")
        for att in atts:
            if not att.datas:
                continue
            try:
                tree = etree.fromstring(base64.b64decode(att.datas))
            except Exception:
                continue
            if tree.find(".//tfd:TimbreFiscalDigital", CFDI_NS) is not None:
                return tree
        return None

    def _aq_get_cfdi_data(self):
        self.ensure_one()
        comp = self._aq_get_cfdi_xml()
        if comp is None:
            return {}
        tfd = comp.find(".//tfd:TimbreFiscalDigital", CFDI_NS)
        emi = comp.find("cfdi:Emisor", CFDI_NS)
        rec = comp.find("cfdi:Receptor", CFDI_NS)
        if tfd is None:
            return {}

        g = lambda n, a, d="": (n.get(a, d) if n is not None else d)
        uuid = tfd.get("UUID", "")
        sello_cfdi = comp.get("Sello", "")
        rfc_emi = g(emi, "Rfc")
        rfc_rec = g(rec, "Rfc")
        total = comp.get("Total", "0")
        fe = sello_cfdi[-8:] if sello_cfdi else ""

        qr_value = "%s?id=%s&re=%s&rr=%s&tt=%s&fe=%s" % (
            SAT_URL, uuid, rfc_emi, rfc_rec, total, fe,
        )

        # Conceptos
        conceptos = []
        for c in comp.findall("cfdi:Conceptos/cfdi:Concepto", CFDI_NS):
            traslados = []
            for t in c.findall("cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", CFDI_NS):
                tasa = t.get("TasaOCuota", "")
                tasa_disp = tasa
                if t.get("TipoFactor") == "Tasa":
                    try:
                        tasa_disp = "%.2f%%" % (float(tasa) * 100)
                    except (TypeError, ValueError):
                        pass
                traslados.append({
                    "impuesto": t.get("Impuesto", ""),
                    "impuesto_nombre": IMP_NAMES.get(t.get("Impuesto", ""), t.get("Impuesto", "")),
                    "base": t.get("Base", ""),
                    "tipo_factor": t.get("TipoFactor", ""),
                    "tasa": tasa,
                    "tasa_disp": tasa_disp,
                    "importe": t.get("Importe", ""),
                })
            conceptos.append({
                "clave_prod": c.get("ClaveProdServ", ""),
                "no_id": c.get("NoIdentificacion", ""),
                "cantidad": c.get("Cantidad", ""),
                "clave_unidad": c.get("ClaveUnidad", ""),
                "unidad": c.get("Unidad", ""),
                "descripcion": c.get("Descripcion", ""),
                "valor_unitario": c.get("ValorUnitario", ""),
                "importe": c.get("Importe", ""),
                "descuento": c.get("Descuento", "") or "0.00",
                "objeto_imp": c.get("ObjetoImp", ""),
                "traslados": traslados,
            })

        cadena_sat = "||%s|%s|%s|%s|%s|%s||" % (
            tfd.get("Version", "1.1"),
            uuid,
            tfd.get("FechaTimbrado", ""),
            tfd.get("RfcProvCertif", ""),
            tfd.get("SelloCFD", sello_cfdi),
            tfd.get("NoCertificadoSAT", ""),
        )

        reg_emi = g(emi, "RegimenFiscal")
        reg_rec = g(rec, "RegimenFiscalReceptor")
        uso = g(rec, "UsoCFDI")
        tipo = comp.get("TipoDeComprobante", "")

        return {
            "uuid": uuid,
            "version": comp.get("Version", ""),
            "serie": comp.get("Serie", ""),
            "folio": comp.get("Folio", ""),
            "fecha": comp.get("Fecha", "").replace("T", " "),
            "sello_cfdi": sello_cfdi,
            "sello_sat": tfd.get("SelloSAT", ""),
            "no_certificado": comp.get("NoCertificado", ""),
            "no_certificado_sat": tfd.get("NoCertificadoSAT", ""),
            "rfc_pac": tfd.get("RfcProvCertif", ""),
            "fecha_timbrado": tfd.get("FechaTimbrado", "").replace("T", " "),
            "rfc_emisor": rfc_emi,
            "nombre_emisor": g(emi, "Nombre"),
            "regimen_emisor": reg_emi,
            "regimen_emisor_nombre": REGIMEN.get(reg_emi, reg_emi),
            "rfc_receptor": rfc_rec,
            "nombre_receptor": g(rec, "Nombre"),
            "cp_receptor": g(rec, "DomicilioFiscalReceptor"),
            "regimen_receptor": reg_rec,
            "regimen_receptor_nombre": REGIMEN.get(reg_rec, reg_rec),
            "uso_cfdi": uso,
            "uso_cfdi_nombre": USO_CFDI.get(uso, uso),
            "lugar_expedicion": comp.get("LugarExpedicion", ""),
            "tipo_comprobante": tipo,
            "tipo_comprobante_nombre": TIPO_COMPROBANTE.get(tipo, tipo),
            "exportacion": comp.get("Exportacion", ""),
            "moneda": comp.get("Moneda", ""),
            "forma_pago": comp.get("FormaPago", ""),
            "metodo_pago": comp.get("MetodoPago", ""),
            "subtotal": comp.get("SubTotal", ""),
            "descuento": comp.get("Descuento", ""),
            "total": total,
            "conceptos": conceptos,
            "cadena_sat": cadena_sat,
            "qr_value": qr_value,
            "qr_b64": self._aq_qr_b64(qr_value),
        }

    def _aq_qr_b64(self, value):
        if not qrcode or not value:
            return ""
        try:
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10, border=1,
            )
            qr.add_data(value)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
        except Exception:
            _logger.exception("No se pudo generar el QR del CFDI")
            return ""
