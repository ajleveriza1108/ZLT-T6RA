def mock_summary() -> dict:
    contexts = [
        {
            "cid": 1,
            "pdp_type": "IPV4V6",
            "apn": "internet.globe.com.ph",
            "pdp_address": "0.0.0.0",
            "active": True,
            "addresses": ["10.113.76.24", "2001:4458:204:3100::682f"],
        },
        {
            "cid": 9,
            "pdp_type": "IPV4V6",
            "apn": "ims",
            "pdp_address": "0.0.0.0",
            "active": True,
            "addresses": ["10.95.201.12"],
        },
    ]

    return {
        "device": "ZLT T6R-A",
        "connected": True,
        "mode": "mock",
        "port": "COM12",
        "operator": "Globe Telecom-PH",
        "rat": "LTE",
        "cfun": 1,
        "sim_status": "READY",
        "registered": True,
        "packet_attached": True,
        "csq": 29,
        "hcsq": {
            "rat": "LTE",
            "raw_values": [80, 65, 160, 30],
            "raw": '^HCSQ:"LTE",80,65,160,30',
        },
        "sysinfoex": '^SYSINFOEX:2,3,0,1,,6,"LTE",101,"LTE"',
        "contexts": contexts,
        "apn": "internet.globe.com.ph",
        "ipv4": "10.113.76.24",
        "pdp_active": True,
        "raw": {
            "cfun": "+CFUN: 1\r\n\r\nOK",
            "cpin": "+CPIN: READY\r\n\r\nOK",
            "operator": '+COPS: 0,0,"Globe Telecom-PH",7\r\n\r\nOK',
            "cereg": "+CEREG: 0,1\r\n\r\nOK",
            "cgreg": "+CGREG: 0,1\r\n\r\nOK",
            "attach": "+CGATT: 1\r\n\r\nOK",
            "signal": "+CSQ: 29,99\r\n\r\nOK",
            "contexts": '+CGDCONT: 1,"IPV4V6","internet.globe.com.ph","0.0.0.0"\r\n+CGDCONT: 9,"IPV4V6","ims","0.0.0.0"\r\n\r\nOK',
        },
    }


def mock_networks() -> list[dict]:
    return [
        {"operator": "Globe Telecom-PH", "numeric": "51502", "rat": "LTE", "status": "Current"},
        {"operator": "Smart", "numeric": "51503", "rat": "LTE", "status": "Forbidden"},
        {"operator": "DITO", "numeric": "51566", "rat": "LTE", "status": "Available"},
        {"operator": "ISLACOM", "numeric": "51505", "rat": "LTE", "status": "Available"},
    ]
