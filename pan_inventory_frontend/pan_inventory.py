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
import prettytable
from pymongo import MongoClient
from flask import Flask, render_template
from flask_bootstrap import Bootstrap
import config

app = Flask(__name__)
bootstrap = Bootstrap(app)


def update_html(html):
    '''
    Updates the tables to include thead and tbody tags
    '''
    html_list = html.splitlines()
    updated_html = ' '.join([item.lstrip() for item in html_list])

    # Adds thead open tag at the start of table head
    thead_start_fixed = re.sub(r'(<table\s[id|class].*\s[id|class].*>)\s(<tr>\s<th>)', r'\1 <thead> \2', updated_html)

    # Adds thead close tag at the end of table head
    thead_end_fixed = re.sub(r'(<\/th>\s<\/tr>)', r'\1 </thead>', thead_start_fixed)

    # Adds tbody open tag at the start of table body
    tbody_start_fixed = re.sub(r'(<\/thead>)\s(<tr>\s<td>)', r'\1 <tbody> \2', thead_end_fixed)

    # Adds tbody close tag at the end of table body
    tbody_end_fixed = re.sub(r'(<\/tr>)\s(<\/table>)', r'\1 </tbody> \2', tbody_start_fixed)

    return tbody_end_fixed


@app.route("/")
def palo_inventory():
    '''
    Connects to MongoDB and uses 'inventory' database and 'paloalto' collection
    to gather Palos inventory data for display using Flask
    '''
    try:
        username = config.mongo['read_username']
        password = config.mongo['read_password']
        mongodb_ip = config.mongo['mongodb_ip']
        mongodb_port = config.mongo['mongodb_port']

        client = MongoClient(
            host=mongodb_ip,
            port=mongodb_port,
            username=username,
            password=password
        )
    except pymongo.errors.ConnectionFailure as error:
        print('Could not connect to MongoDB: {}'.format(error))
    else:
        db = client['inventory']
        collection = db['paloalto']

        find_results = collection.find()

        main_table = prettytable.PrettyTable(['Hostname', 'IP Address', 'Serial Number', 'Model', 'Software Version'])

        parts_table = prettytable.PrettyTable(['Hostname', 'Description', 'Serial Number', 'Model', 'Slot'])

        for device_dict in find_results:
            hostname = device_dict.get('hostname')
            ip_address = device_dict.get('ip-address')
            serial = device_dict.get('serial')
            model = device_dict.get('model')
            sw_version = device_dict.get('sw-version')
            family = device_dict.get('family')

            main_table.add_row([hostname, ip_address, serial, model, sw_version])

            if family == '7000':
                chassis_list = device_dict.get('chassis')
                for chassis_dict in chassis_list:
                    chassis_slot = chassis_dict.get('slot')
                    chassis_model = chassis_dict.get('model')
                    chassis_type = chassis_dict.get('type')
                    chassis_serial = chassis_dict.get('serial')
                    parts_table.add_row([hostname, chassis_type, chassis_serial, chassis_model, chassis_slot])

                powersupply_list = device_dict.get('power-supply')
                for powersupply_dict in powersupply_list:
                    powersupply_model = powersupply_dict.get('model')
                    powersupply_serial = powersupply_dict.get('serial')
                    powersupply_desc = powersupply_dict.get('desc')
                    parts_table.add_row([hostname, powersupply_desc, powersupply_serial, powersupply_model, "N/A"])

                fantray_list = device_dict.get('fantray')
                for fantray_dict in fantray_list:
                    fantray_model = fantray_dict.get('model')
                    fantray_serial = fantray_dict.get('serial')
                    fantray_desc = fantray_dict.get('desc')
                    parts_table.add_row([hostname, fantray_desc, fantray_serial, fantray_model, "N/A"])

                amc_list = device_dict.get('amc')
                for amc_dict in amc_list:
                    amc_serial = amc_dict.get('serial')
                    amc_desc = amc_dict.get('desc')
                    parts_table.add_row([hostname, amc_desc, amc_serial, "N/A", "N/A"])

        main_table_html = main_table.get_html_string(attributes={"id": "main_table", "class": "display"})
        parts_table_html = parts_table.get_html_string(attributes={"id": "parts_table", "class": "display"})

        main_table_html_updated = update_html(main_table_html)
        parts_table_html_updated = update_html(parts_table_html)

        return render_template('inventory.html', main_table=main_table_html_updated, parts_table=parts_table_html_updated)


if __name__ == '__main__':
    app.run()
