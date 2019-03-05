#!/usr/bin/env python

# Copyright (c) 2019 Brad Atkinson <brad.scripting@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import re
import os
import logging
import logging.handlers as handlers
from pandevice import panorama
from pandevice import firewall
from pymongo import MongoClient
import pan_module as pa
import config

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s   Log Level: %(levelname)-8s   Line: %(lineno)-3d   Function: %(funcName)-21s   Msg: %(message)s', datefmt='%m/%d %I:%M:%S %p')

log_dir = config.directories['log']
log_file = (os.path.join(log_dir, 'pa_inventory.log'))
log_handler = handlers.TimedRotatingFileHandler(
    log_file,
    when='midnight',
    backupCount=2
)
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)

error_log_file = (os.path.join(log_dir, 'pa_inventory_errors.log'))
error_log_handler = handlers.TimedRotatingFileHandler(
    error_log_file,
    when='midnight',
    backupCount=2
)
error_log_handler.setLevel(logging.ERROR)
error_log_handler.setFormatter(formatter)
logger.addHandler(error_log_handler)


def get_connected_devices(pano, collection):
    """
    Get the connected devices info from Panorama and adds/updates database
    with serial number, hostname, family, model, and ip of firewall

    Parameters
    ----------
    pano : Panorama
        A PanDevice for Panorama
    collection : Collection
        A MongoDB database collection

    Returns
    -------
    device_dict : dict
        A dictionary of Panorama connected devices, in format of
            dict: {
                'serial_number': {
                    'ip_address': str,
                    'model': str
                    }
            }
    """
    logger.info('Getting connected devices')
    results = pano.op('show devices connected')

    device_dict = {}

    devices_xml_list = results.findall('./result/devices/entry')

    for device in devices_xml_list:
        serial = device.find('./serial').text
        hostname = device.find('./hostname').text
        ip_addr = device.find('./ip-address').text
        family = device.find('./family').text
        model = device.find('./model').text
        sw_version = device.find('./sw-version').text

        if family == '7000':
            device_dict[serial] = {'ip-address': ip_addr,
                                   'model': model}

        find_results = collection.find_one(
            {'ip-address': ip_addr},
            {'serial': 1, 'sw-version': 1, '_id': 0}
        )
        logger.debug(find_results)

        if find_results is None:
            insert_results = collection.insert(
                {
                    'serial': serial,
                    'hostname': hostname,
                    'ip-address': ip_addr,
                    'family': family,
                    'model': model,
                    'sw-version': sw_version
                }
            )
            logger.debug(insert_results)
        else:
            stored_serial = find_results.get('serial')
            if stored_serial != serial:
                update_serial = collection.update_one(
                    {"ip-address": ip_addr},
                    {'$set': {'serial': serial}}
                )
                logger.debug('Update Serial Number -- Matched: {} -- Modified: {}'.format(update_serial.matched_count, update_serial.modified_count))

        stored_sw_version = find_results.get('sw-version')
        if stored_sw_version != sw_version:
            update_sw_version = collection.update_one(
                {"ip-address": ip_addr},
                {'$set': {'sw-version': sw_version}}
            )
            logger.debug('Update Software Version -- Matched: {} -- Modified: {}'.format(update_sw_version.matched_count, update_sw_version.modified_count))

    logger.debug(device_dict)
    return device_dict


def get_7K_info(device_dict, collection):
    """
    Checks Palo firewall to see if model and family are in the 7K family,
    sets variables, and then gets 7K info

    Parameters
    ----------
    device_dict : dict
        A dictionary of Panorama connected devices
    collection : Collection
        A MongoDB database collection
    """
    logger.info('Starting')

    key = config.paloalto['key']

    for device in device_dict:
        fw_dict = device_dict.get(device)
        model = fw_dict.get('model')
        ip_addr = fw_dict.get('ip-address')

        if model == 'PA-7080':
            smc_slot = '6'
            lpc_slot = '7'
            ps_total = 8
            slot_total = 12
        elif model == 'PA-7050':
            smc_slot = '4'
            lpc_slot = '8'
            ps_total = 4
            slot_total = 8

        fw = firewall.Firewall(hostname=ip_addr, api_key=key)
        get_7K_chassis_info(fw, collection, ip_addr, slot_total)
        get_7K_power_info(fw, collection, ip_addr, smc_slot, ps_total)
        get_7K_fan_info(fw, collection, ip_addr, smc_slot)
        get_7K_amc_info(fw, collection, ip_addr, lpc_slot)


def get_7K_chassis_info(fw, collection, ip_addr, slot_total):
    """
    Gets Palo 7K chassis info if chassis slot is occupied and adds/updates
    database

    Parameters
    ----------
    fw : Firewall
        A PanDevice for the firewall
    collection : Collection
        A MongoDB database collection
    ip_addr : str
        The IP address of the firewall
    slot_total : int
        The total number of slots in the chassis
    """
    logger.info('Starting')
    for num in range(1, (slot_total + 1)):
        chassis_cmd = ('<show><system><state><filter>chassis.s{}.info'
                       '</filter></state></system></show>'.format(str(num)))
        results = fw.op(cmd=chassis_cmd, cmd_xml=False, xml=True)
        chassis_info = re.search(r"'model':\s(.*),\s'port_cnt':.*'serial':\s(.*),\s'slot':\s(.*),\s'type':\s(.*),\s'version'", results)

        if chassis_info is not None:
            chassis_type = chassis_info.group(4)
            if chassis_type != 'Empty':
                model = chassis_info.group(1)
                serial = chassis_info.group(2)
                slot = chassis_info.group(3)

                find_results = collection.find_one(
                    {'ip-address': ip_addr},
                    {
                        'chassis': {
                            '$elemMatch': {
                                'slot': slot,
                                'model': model
                            }
                        },
                        '_id': 0
                    }
                )
                logger.debug(find_results)

                if find_results is None:
                    update_results = collection.update_one(
                        {'ip-address': ip_addr},
                        {'$addToSet': {'chassis': {
                            'model': model,
                            'serial': serial,
                            'slot': slot,
                            'type': chassis_type
                        }}}
                    )
                    logger.debug('Matched: {} -- Modified: {}'.format(update_results.matched_count, update_results.modified_count))
                else:
                    chassis_dict = find_results.get('chassis')[0]
                    stored_serial = chassis_dict.get('serial')
                    stored_slot = chassis_dict.get('slot')

                    if stored_slot == slot and stored_serial != serial:
                        update_results = collection.update_one(
                            {'ip-address': ip_addr, 'chassis.slot': slot},
                            {'$set': {'chassis.$.serial': serial}}
                        )
                        logger.debug('Update Chassis Card Serial Number -- Matched: {} -- Modified: {}'.format(update_results.matched_count, update_results.modified_count))


def get_7K_power_info(fw, collection, ip_addr, smc_slot, ps_total):
    """
    Gets Palo 7K power supply info if present and adds/updates database

    Parameters
    ----------
    fw : Firewall
        A PanDevice for the firewall
    collection : Collection
        A MongoDB database collection
    ip_addr : str
        The IP address of the firewall
    smc_slot : str
        The SMC (Switch Management Card) slot location in the chassis
    ps_total : int
        The total number of power supplies in the chassis
    """
    logger.info('Starting')
    for num in range(0, ps_total):
        power_cmd = ('<show><system><state><filter>env.s{}.power-supply.{}'
                     '</filter></state></system></show>'
                     .format(smc_slot, str(num)))
        results = fw.op(cmd=power_cmd, cmd_xml=False, xml=True)
        ps_info = re.search(r"'desc':\s(.*),\s'max-pwr':.*'model-no':\s(.*),\s'present':\s(.*),\s'serial-no':\s(.*),\s'version'", results)

        if ps_info is not None:
            ps_present = ps_info.group(3)
            if ps_present == 'True':
                desc = ps_info.group(1)
                model = ps_info.group(2)
                serial = ps_info.group(4)

                find_results = collection.find_one(
                    {'ip-address': ip_addr},
                    {'power-supply': {'$elemMatch': {'desc': desc}}, '_id': 0}
                )
                logger.debug(find_results)

                if find_results is None:
                    update_results = collection.update_one(
                        {"ip-address": ip_addr},
                        {'$addToSet': {'power-supply': {
                            'model': model,
                            'serial': serial,
                            'desc': desc
                        }}}
                    )
                    logger.debug('Matched: {} -- Modified: {}'.format(update_results.matched_count, update_results.modified_count))
                else:
                    powersupply_dict = find_results.get('power-supply')[0]
                    stored_serial = powersupply_dict.get('serial')
                    stored_desc = powersupply_dict.get('desc')

                    if stored_desc == desc and stored_serial != serial:
                        update_results = collection.update_one(
                            {'ip-address': ip_addr, 'power-supply.desc': desc},
                            {'$set': {'power-supply.$.serial': serial}}
                        )
                        logger.debug('Update Power Supply Serial Number -- Matched: {} -- Modified: {}'.format(update_results.matched_count, update_results.modified_count))


def get_7K_fan_info(fw, collection, ip_addr, smc_slot):
    """
    Gets Palo 7K fantray info if present and adds/updates database

    Parameters
    ----------
    fw : Firewall
        A PanDevice for the firewall
    collection : Collection
        A MongoDB database collection
    ip_addr : str
        The IP address of the firewall
    smc_slot : str
        The SMC (Switch Management Card) slot location in the chassis
    """
    logger.info('Starting')
    for num in range(0, 2):
        fantray_present_cmd = ('<show><system><state><filter>env.s{}.'
                               'fantray-present.{}</filter></state></system>'
                               '</show>'.format(smc_slot, str(num)))
        results = fw.op(cmd=fantray_present_cmd, cmd_xml=False, xml=True)
        fantray_present = re.sub(r'<response status="success"><result>env.s[4,6].fantray-present.[0-1]: ', '', results)
        fantray_present = re.sub(r'\n</result></response>', '', fantray_present)

        if fantray_present == 'True':
            fantray_cmd = ('<show><system><state><filter>env.s{}.fantray.{}'
                           '</filter></state></system></show>'
                           .format(smc_slot, str(num)))
            fantray = fw.op(cmd=fantray_cmd, cmd_xml=False, xml=True)
            fantray_info = re.search(r"'desc':\s(.*),\s'min':.*'pan-model-no':\s(.*),\s'pan-serial-no':\s(.*),\s'power'", fantray)

            if fantray_info is not None:
                desc = fantray_info.group(1)
                model = fantray_info.group(2)
                serial = fantray_info.group(3)

                find_results = collection.find_one(
                    {'ip-address': ip_addr},
                    {'fantray': {'$elemMatch': {'desc': desc}}, '_id': 0}
                )
                logger.debug(find_results)

                if find_results is None:
                    update_results = collection.update_one(
                        {"ip-address": ip_addr},
                        {'$addToSet': {'fantray': {
                            'model': model,
                            'serial': serial,
                            'desc': desc
                        }}}
                    )
                    logger.debug('Matched: {} -- Modified: {}'.format(update_results.matched_count, update_results.modified_count))
                else:
                    fantray_dict = find_results.get('fantray')[0]
                    stored_serial = fantray_dict.get('serial')
                    stored_desc = fantray_dict.get('desc')

                    if stored_desc == desc and stored_serial != serial:
                        update_results = collection.update_one(
                            {'ip-address': ip_addr, 'fantray.desc': desc},
                            {'$set': {'fantray.$.serial': serial}}
                        )
                        logger.debug('Update Fantray Serial Number -- Matched: {} -- Modified: {}'.format(update_results.matched_count, update_results.modified_count))


def get_7K_amc_info(fw, collection, ip_addr, lpc_slot):
    """
    Gets Palo 7K AMC (Advanced Mezzanine Card) disk drive info and
    adds/updates database

    Parameters
    ----------
    fw : Firewall
        A PanDevice for the firewall
    collection : Collection
        A MongoDB database collection
    ip_addr : str
        The IP address of the firewall
    lpc_slot : str
        The LPC (Log Processing Card) slot location in the chassis
    """
    logger.info('Starting')
    for num in range(0, 4):
        amc_cmd = ('<show><system><state><filter>env.s{}.raid.{}</filter>'
                   '</state></system></show>'.format(lpc_slot, str(num)))
        results = fw.op(cmd=amc_cmd, cmd_xml=False, xml=True)
        hd_info = re.search(r"'desc':\s(.*)\sstatus,\s'min':.*'serial-no':\s(.*),\s", results)

        if hd_info is not None:
            desc = hd_info.group(1)
            serial = hd_info.group(2)

            find_results = collection.find_one(
                {'ip-address': ip_addr},
                {'amc': {'$elemMatch': {'desc': desc}}, '_id': 0}
            )
            logger.debug(find_results)

            if find_results is None:
                update_results = collection.update_one(
                    {"ip-address": ip_addr},
                    {'$addToSet': {'amc': {'serial': serial, 'desc': desc}}}
                )
                logger.debug('Matched: {} -- Modified: {}'.format(update_results.matched_count, update_results.modified_count))
            else:
                amc_dict = find_results.get('amc')[0]
                stored_serial = amc_dict.get('serial')
                stored_desc = amc_dict.get('desc')

                if stored_desc == desc and stored_serial != serial:
                    update_results = collection.update_one(
                        {'ip-address': ip_addr, 'amc.desc': desc},
                        {'$set': {'amc.$.serial': serial}}
                    )
                    logger.debug('Update AMC Serial Number -- Matched: {} -- Modified: {}'.format(update_results.matched_count, update_results.modified_count))


def get_pano_info(collection):
    """
    Gets Palo Panorama info and adds/updates database

    Parameters
    ----------
    collection : Collection
        A MongoDB database collection
    """
    logger.info('Starting')

    key = config.paloalto['key']
    panorama_ips = config.paloalto['panorama_ips']

    for ip in panorama_ips:
        logger.debug(ip)
        pano = panorama.Panorama(hostname=ip, api_key=key)

        results = pano.op('show system info')

        serial = results.find('./result/system/serial').text
        hostname = results.find('./result/system/hostname').text
        ip_addr = results.find('./result/system/ip-address').text
        family = results.find('./result/system/family').text
        model = results.find('./result/system/model').text
        sw_version = results.find('./result/system/sw-version').text

        find_results = collection.find_one(
            {"ip-address": ip_addr},
            {'serial': 1, 'sw-version': 1, '_id': 0}
        )
        logger.debug(find_results)

        if find_results is None:
            insert_results = collection.insert(
                {
                    'serial': serial,
                    'hostname': hostname,
                    'ip-address': ip_addr,
                    'family': family,
                    'model': model,
                    'sw-version': sw_version
                }
            )
            logger.debug(insert_results)
        else:
            stored_serial = find_results.get('serial')
            if stored_serial != serial:
                update_serial = collection.update_one(
                    {"ip-address": ip_addr},
                    {'$set': {'serial': serial}}
                )
                logger.debug('Update Serial Number -- Matched: {} -- Modified: {}'.format(update_serial.matched_count, update_serial.modified_count))

        stored_sw_version = find_results.get('sw-version')
        if stored_sw_version != sw_version:
            update_sw_version = collection.update_one(
                {"ip-address": ip_addr},
                {'$set': {'sw-version': sw_version}}
            )
            logger.debug('Update Software Version -- Matched: {} -- Modified: {}'.format(update_sw_version.matched_count, update_sw_version.modified_count))


def main():
    """
    Connects to MongoDB and uses 'inventory' database and 'paloalto' collection
    to capture all connected Palos inventory data
    """
    logger.info('Starting')

    try:
        username = config.mongo['write_username']
        password = config.mongo['write_password']
        mongodb_ip = config.mongo['mongodb_ip']
        mongodb_port = config.mongo['mongodb_port']

        client = MongoClient(
            host=mongodb_ip,
            port=mongodb_port,
            username=username,
            password=password
        )

        logger.debug('Connected to MongoDB successfully')
    except pymongo.errors.ConnectionFailure as error:
        logger.error('Could not connect to MongoDB: {}'.format(error))
    else:
        db = client['inventory']
        collection = db['paloalto']

        pano = pa.get_active_pano()
        device_dict = get_connected_devices(pano, collection)
        get_7K_info(device_dict, collection)
        get_pano_info(collection)


if __name__ == '__main__':
    main()
