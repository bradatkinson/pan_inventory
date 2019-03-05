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
import config
from pandevice import panorama


def get_active_pano():
    """
    Read Panorama IPs from file, for each IP make Panorama connection, get
    HA status, and then return the active device

    Returns
    -------
    pano : Panorama
         A PanDevice for Panorama
    """
    key = config.paloalto['key']
    panorama_ips = config.paloalto['panorama_ips']

    if len(panorama_ips) == 1:
        pano = panorama.Panorama(hostname=panorama_ips[0], api_key=key)
        return pano
    else:
        for ip in panorama_ips:
            pano = panorama.Panorama(hostname=ip, api_key=key)
            ha_status = get_ha_status(pano)
            if ha_status == 'active':
                return pano


def get_ha_status(pano):
    """
    Gets the panorama state (active/passive/suspended) via the API and
    returns the HA status

    Strips possible results of primary-active, primary-passive,
    primary-suspended, secondary-active, secondary-passive, and
    secondary-suspended to only give status as active, passive, or
    suspended

    Parameters
    ----------
    pano : Panorama
        A PanDevice for Panorama

    Returns
    -------
    ha_status : str
        The high availability status of Panorama
    """
    command = ('<show><system><state><filter>ha.app.cli.state-prompt'
               '</filter></state></system></show>')
    results = pano.op(cmd=command, cmd_xml=False, xml=True)

    if 'primary' in results:
        ha_status = re.sub('<response status="success"><result>'
                           'ha.app.cli.state-prompt: primary-', '', results)
    elif 'secondary' in results:
        ha_status = re.sub('<response status="success"><result>'
                           'ha.app.cli.state-prompt: secondary-', '', results)

    ha_status = re.sub('\n</result></response>', '', ha_status)

    return ha_status


def get_connected_devices(pano):
    """
    Get the connected devices info from Panorama and adds/updates database
    with serial number, hostname, family, model, and ip of firewall

    Parameters
    ----------
    pano : Panorama
        A PanDevice for Panorama

    Returns
    -------
    device_dict : dict
        A dictionary of Panorama connected devices, in format of
            dict: {
                'serial_number': {
                    'hostname': str,
                    'ip_address': str,
                    'family': str,
                    'model': str,
                    'software_version': str
                    }
            }
    """
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

        device_dict[serial] = {'hostname': hostname,
                               'ip-address': ip_addr,
                               'serial': serial,
                               'family': family,
                               'model': model,
                               'sw-version': sw_version}

    return device_dict
