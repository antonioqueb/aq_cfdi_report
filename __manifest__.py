# -*- coding: utf-8 -*-
{
    "name": "Alphaqueb - Representación impresa CFDI",
    "summary": "Formato limpio de factura CFDI 4.0 con QR, leyendo el XML timbrado (PAC-agnóstico).",
    "version": "19.0.1.0.0",
    "author": "Alphaqueb Consulting SAS",
    "license": "LGPL-3",
    "category": "Accounting/Localizations",
    "depends": ["account"],
    "data": [
        "report/report_action.xml",
        "report/report_cfdi_template.xml",
    ],
    "external_dependencies": {"python": ["qrcode"]},
    "installable": True,
    "application": False,
}
