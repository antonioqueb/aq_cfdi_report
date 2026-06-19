# -*- coding: utf-8 -*-
{
    "name": "Alphaqueb - Representación impresa CFDI",
    "summary": "Formato limpio de factura CFDI 4.0 con QR, leyendo el XML timbrado (PAC-agnóstico).",
    "version": "19.0.1.0.2",
    "author": "Alphaqueb Consulting SAS",
    "license": "LGPL-3",
    "category": "Accounting/Localizations",
    "depends": ["account", "l10n_mx_edi", "sale"],
    "data": [
        "report/report_disable_l10n_mx.xml",
        "report/report_cfdi_template.xml",
        "report/report_saleorder_template.xml",
    ],
    "external_dependencies": {"python": ["qrcode"]},
    "installable": True,
    "application": False,
}
