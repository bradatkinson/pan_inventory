# pan_inventory_backend

The purpose of this script is to collect all inventory information from the Palo Alto Networks Panorama and firewalls. Common info such as hostname, IP address, serial number, model, family, and software version are collected using the API from the _show devices connected_ command. For the 7000 series firewalls additional information is collected for fan trays, power supplies, hard drives, and chassis slot cards. All this information is updated in a MongoDB database named __inventory__ using the collection __paloaltonetworks__.

## Built With

[Palo Alto Networks Device Framework (pandevice)](https://github.com/PaloAltoNetworks/pandevice)\
[PyMongo - MongoDB API](https://api.mongodb.com/python/current/)

## Deployment

All files within the folder should be deployed in the same directory for proper file execution.

## Prerequisites

Update `config.py` file with correct values before operating.

## Operating

The below command will execute the script.

```bash
python pan_inventory.py
```

## Database

The data collected from this script is stored in a MongoDB database. The database is named __inventory__ and the collection is named __paloaltonetworks__.

### Schema

#### PA-3000/PA-5000 series

```json
{
    "family" : "<FAMILY>",
    "sw-version" : "<SOFTWARE_VERSION>",
    "hostname" : "<FIREWALL_NAME>",
    "ip-address" : "<IP_ADDRESS>",
    "model" : "<MODEL>",
    "serial" : "<SERIAL_NO>"
}
```

#### PA-7000 series

```json
{
    "family" : "<FAMILY>",
    "sw-version" : "<SOFTWARE_VERSION>",
    "hostname" : "<FIREWALL_NAME>",
    "ip-address" : "<IP_ADDRESS>",
    "model" : "<MODEL>",
    "serial" : "<SERIAL_NO>",
    "chassis" : [ { "slot" : "1", "model" : "PA-7000-20GQ-NPC", "type" : "20GQ", "serial" : "<SERIAL_NO>" }, { "slot" : "4", "model" : "PA-7050-SMC", "type" : "SwitchManagement", "serial" : "<SERIAL_NO>" }, { "slot" : "8", "model" : "PA-7000-LPC", "type" : "LogProcessor", "serial" : "<SERIAL_NO>" } ],
    "power-supply" : [ { "model" : "<MODEL>", "serial" : "<SERIAL_NO>", "desc" : "Power Supply #1" }, { "model" : "<MODEL>", "serial" : "<SERIAL_NO>", "desc" : "Power Supply #2" }, { "model" : "<MODEL>", "serial" : "<SERIAL_NO>", "desc" : "Power Supply #3" }, { "model" : "<MODEL>", "serial" : "<SERIAL_NO>", "desc" : "Power Supply #4" } ],
    "fantray" : [ { "model" : "PA-7050-FANTRAY", "serial" : "<SERIAL_NO>", "desc" : "Fan Tray #1 (Left)" }, { "model" : "PA-7050-FANTRAY", "serial" : "<SERIAL_NO>", "desc" : "Fan Tray #2 (Right)" } ],
    "amc" : [ { "serial" : "<SERIAL_NO>", "desc" : "Card 1" }, { "serial" : "<SERIAL_NO>", "desc" : "Card 2" }, { "serial" : "<SERIAL_NO>", "desc" : "Card 3" }, { "serial" : "<SERIAL_NO>", "desc" : "Card 4" } ]
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
