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
            "attach": "+CGATT: 1\r\n\r\nOK",
            "signal": "+CSQ: 29,99\r\n\r\nOK",
        },
    }
