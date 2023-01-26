import requests
import xml.etree.ElementTree as ET  # built-in xml parsing library
import datetime
COGECO_ID = 469370
GROUP_NAME = 'COGECO'

#GROUP_NAME= 'COGECO_NEW'
#COGECO_ID= 518799

time_string = str(datetime.datetime.now().date()) + str(datetime.datetime.now().time().hour) + str(datetime.datetime.now().time().minute)
LOG_FILE_NAME = f"post_new_logs_{time_string}.txt"  # TODO 4, Also log deleted groups in the file

EVERYTHING_LOG_FILE_NAME = f"post_everything_logs_{time_string}.txt"  # TODO 4, Also log deleted groups in the file
DELETE_LOG_FILE_NAME = f"delete_logs_{time_string}.txt"

HEADERS = {
  'Authorization': 'Basic U2VydmljZU5vd19BUElVc2VyOjEyM19hYmNf',
  'Cookie': 'JSESSIONID=node0wipolprcmk6217etx46qhfzmg670.node0'
}

class InventoryNewToCogeco:

    def __init__(self):
        self.response_string = ''  # the response text from get request to inventory
        self.inventory_name_id_dict = {}  # key value pairs: service_name: service_id
        self.inventory_name_circuit_id_dict = {}  # key value pairs: service_name: circuit_name [inside brackets]
        self.services = []  # list of all service names in inventory
        # count no of groups posted
        self.post_counter = 0  # used to count the number of groups posted in POST request
        # initialize the variable for response text from get request to cogeco
        self.cogeco_response_string = ''
        self.new_services = []
        self.cogeco_services = []  # list of all service names in cogeco
        self.cogeco_services_dict = {}  # dict of all service names in cogeco: all service ids in cogeco

        # self.my_file = open(LOG_FILE_NAME, 'w')  # TODO 4
        self.my_file = ''
        self.everything_file = ''
        self.delete_file = ''
        self.is_ok = True



    # send get request and return xml string
    def get_inventory_xml(self):
        url = "https://netops-pm:8182/pc/center/webservice/groups/groupPath/All%20Groups%2FInventory%2FData%20Sources" \
              "%2FSpectrum%20Infrastructure%20Manager@gxpxspcons01%2FAll%20Spectrum%20Global%20Collections "

        payload = {}
        # headers = {
        #     'Authorization': 'Basic YWRtaW46MTIzX2FiY18=',
        #     'Cookie': 'JSESSIONID=node0wxhing3yfvx31rwtvqnnubnop1.node0'
        # }

        headers = HEADERS

        response = requests.request("GET", url, headers=headers, data=payload, verify=False)

        self.is_ok = response.ok
        self.status_code = response.status_code
        self.reason = response.reason

        # assigns the xml response text to shared class variable
        self.response_string = response.text
        return self.response_string  # returns xml response text

    # parse xml and put inventory data in a dict
    def populate_inventory_data(self):
        inventory_name_id_dict = {}  # Creating a dictionary to store key:Service_name -value : group_id
        inventory_name_circuit_id_dict = {}  # # Creating a dictionary to store key:Service_name -value : circuit_id
        services = []

        # select the root element of xml (which is All spectrum global collections)
        root = ET.fromstring(self.response_string)

        # For every group in GroupTree (All spectrum global collection)
        for group in root.findall('Group'):

            # Access each group individual
            name = group.get('name')  # Get the name attribute of the selected group
            group_id = group.get('id')  # Get the id attribute of the selected group

            # skip if & is present in name (because it can cause errors when posting xml)
            # todo 10 jun log skipped to a file as well
            f = open('skipped_names.txt', 'w')
            if name.find('&') != -1:
                # print(f'SKIPPED {name}') todo 24 jun
                f.write(f'SKIPPED {name} reason:& character\n')

                continue

            # Extract circuit_ids from full names
            # For example (DOWLCHSTCHGRINT0001) from -> Service Internet (DOWLCHSTCHGRINT0001)
            bracket_start = name.find('(')
            bracket_end = name.find(')', bracket_start)
            # circuit_id = name[bracket_start + 1: bracket_end]
            if bracket_start != -1 or bracket_end != -1:
                circuit_id = name[bracket_start + 1: bracket_end]
            else:
                # some names don't have circuit ids in parenthesis they are separated by a space character
                # e.g. _Circuit HARRAMERAMSAINT0001

                splitted_name_list = name.split()
                if splitted_name_list[0] == '_Circuit':
                    # extract circuit id
                    circuit_id = splitted_name_list[1]
                else:
                    # print(f'Skipped {name}') # todo 24 jun
                    # todo 10 jun log skipped to a file as well
                    f.write(f'SKIPPED {name} reason: circuit id not found in brackets or after space\n')
                    continue  # skip
            # Till now we have extracted circuit_ids, names and ids

            # populate dictionaries and list mentioned above
            inventory_name_id_dict[name] = group_id
            inventory_name_circuit_id_dict[name] = circuit_id
            services.append(name)

        self.inventory_name_id_dict = inventory_name_id_dict
        self.inventory_name_circuit_id_dict = inventory_name_circuit_id_dict
        self.services = services
        return inventory_name_id_dict, inventory_name_circuit_id_dict

    # post inventory data to cogeco
    # use new services list instead of all services
    def post_inventory_to_cogeco(self, only_new=True):  # only_new is boolean to control all requests vs new requests

        # post payload text starts with GroupTree
        prefix = f'<GroupTree path="/All Groups/{GROUP_NAME}">'  # todo made a change to group name cogeco_test to cogeco_new

        # List that contains all strings (group bodies)
        post_payload_list = [prefix]

        c = 0
        # services contains all services names
        if only_new:
            services = self.new_services
            if not self.new_services:
                print('NO NEW SERVICES RETURNING!')
                self.my_file.write('NO NEW SERVICES FOUND\n')
                return
        else: # not just new, all
            services = self.services

        # reset counter
        self.post_counter = 0
        for service_name in services:

            # for every service name add a group with 3 rules
            assert service_name != ''  # TODO, script testing
            # if c >= 10:
            #     break
            self.post_counter += 1
            post_string = '''
                    <Group name="{name_var}" 
                inherit="false" type="user group" desc="This group was created by python script">
                        <Rules allowDeletes="true" saveRules="true">
                            <Rule add="device" itemSubTypeName="" itemTypeLabel="Device" itemTypeLabels="Devices" name="Add_Devices">
                                <Match>
                                    <Compare readOnly="true" using="MEMBER_OF">
                                        <Property label="Item" name="ItemID" subType="" type="device" typeLabel="Device" typeLabels="Devices"/>
                                        <Value displayValue="/All Groups/Inventory/Data Sources/Spectrum Infrastructure Manager@gxpxspcons01/All Spectrum Global Collections/{name_var}">{value_var}</Value>
                                    </Compare>
                                </Match>
                            </Rule>
                            <Rule add="interface" itemSubTypeName="physical" itemTypeLabel="Interface" itemTypeLabels="Interfaces" name="Add interfaces">
                                <Match>
                                    <Compare readOnly="false" using="LIKE">
                                        <Property label="IfAlias" name="IfAlias" subType="physical" type="interface" typeLabel="Interface" typeLabels="Interfaces"/>
                                        <Value>{circuit_id_var}</Value>
                                    </Compare>
                                </Match>
                            </Rule>
                            <Rule add="component" itemSubTypeName="" itemTypeLabel="Device Component" itemTypeLabels="Device Components" name="Add Components">
                                <Match>
                                    <Compare readOnly="true" using="LIKE">
                                        <Property label="Name" name="ItemName" subType="" type="component" typeLabel="Device Component" typeLabels="Device Components"/>
                                        <Value>{circuit_id_var}</Value>
                                    </Compare>
                                </Match>
                            </Rule>
                        </Rules>
                    </Group>
                '''.format(value_var=self.inventory_name_id_dict[service_name], circuit_id_var=self.inventory_name_circuit_id_dict[service_name], name_var=service_name)

            post_payload_list.append(post_string)  # adding this group string to the list

            c += 1

        postfix = '</GroupTree>'
        post_payload_list.append(postfix)
        post_payload_string = ''.join(post_payload_list)  # converts list to string

        # make post request to this url
        url = f"https://netops-pm:8182/pc/center/webservice/groups/groupItemId/{COGECO_ID}"

        payload = post_payload_string
        # headers = {
        #     'Authorization': 'Basic YWRtaW46MTIzX2FiY18=',
        #     'Content-Type': 'application/xml',
        #     'Cookie': 'JSESSIONID=node0wxhing3yfvx31rwtvqnnubnop1.node0'
        # }
        headers = HEADERS
        headers['Content-Type']='application/xml'

        #print('POST is disabled for testing')
        response = requests.request("POST", url, headers=headers, data=payload.encode('utf-8'), verify=False)

    # make get request to get all cogeco users
    def get_cogeco_xml(self):

        # REQUEST TO COGECO
        url = f"https://Netops-pm:8182/pc/center/webservice/groups/groupPath/All%20Groups%2F{GROUP_NAME}/items"

        payload = {}
        # headers = {
        #     'Authorization': 'Basic YWRtaW46MTIzX2FiY18=',
        #     'Cookie': 'JSESSIONID=node017gawjbip6x821k08vibmrblvv112.node0'
        # }

        headers=HEADERS

        response = requests.request("GET", url, headers=headers, data=payload, verify=False)

        # assigns the xml response text to shared class variable
        self.cogeco_response_string = response.text
        print(self.cogeco_response_string)
        return self.cogeco_response_string  # returns xml response text

    # parse the cogeco xml and use inventory dict to
    # create a dict with new items
    # create_new_name_list is the boolean to control if new name list will be created
    def populate_new_inventory_data(self, create_new_name_list=True):
        new_services = self.new_services
        cogeco_services = self.cogeco_services_dict  # empty dict
        cogeco_services_list = self.cogeco_services
        # select the root element of xml (which is COGECO)
        root = ET.fromstring(self.cogeco_response_string)
        # For every group in GroupTree (All spectrum global collection)

        # PUT ALL COGECO NAMES IN A SET
        # for each <group> tag, which is a service
        new_root = root.find('groups')
        for group in new_root.iter('group'):

            # name attribute from the group tag
            name = group.get('name')
            #cogeco_services.add(name)
            cogeco_services_list.append(name)
            service_id = group.get('id')
            cogeco_services[name] = service_id

        if create_new_name_list:
            # FINDS ALL NAMES WHICH ARE NOT PRESENT IN COGECO AND PUT THEM IN A LIST
            # loop over all inventory items
            for item in self.services:
                # check if item already exists in cogeco set
                if item not in cogeco_services:
                    # print(f'{item} not found in cogeco')
                    new_services.append(item)

    # Delete from cogeco after item has been deleted from inventory ASGC
    def del_cogeco_after_inventory_del(self):
        self.delete_file = open(DELETE_LOG_FILE_NAME, 'w')
        # need to run 4 methods before this: get_inventory_xml(), populate_inventory_data(), inventory.get_cogeco_xml(), inventory.populate_new_inventory_data(False)
        list_of_ids_to_del = []

        # CREATE A LIST OF IDS TO DELETE
        # loop over all items(names list) in cogeco
        for service_name in self.cogeco_services:
            if service_name not in self.inventory_name_id_dict:
                # also delete from cogeco
                # create a list of all ids to be deleted
                service_id = self.cogeco_services_dict[service_name]
                print(f'Will delete {service_name} : {service_id}')
                self.delete_file.write(f'{service_name} : {service_id}\n')
                list_of_ids_to_del.append(service_id)

        #print(list_of_ids_to_del)
        # todo 24 jun
        if not list_of_ids_to_del:
            self.delete_file.write(f'No records were deleted from {GROUP_NAME} because no records were deleted from inventory\n')
        # DELETE REQUEST FOR THESE IDS

        for service_id in list_of_ids_to_del:
            url = f"https://netops-pm:8182/pc/center/webservice/groups/groupItemId/{service_id}/"

            payload = {}

            # headers = {
            #     'Authorization': 'Basic U2VydmljZU5vd19BUElVc2VyOjEyM19hYmNf',
            #     'Cookie': 'JSESSIONID=node0c9dmnhfno7n11b26fzlbb2y1d485.node0'
            # }
            headers = HEADERS

            response = requests.request("DELETE", url, headers=headers, data=payload, verify=False)
            print(f'Response: {response.text}')


def post_everything(inventory):
    inventory.get_inventory_xml()  # run the get function to get inventory ASGC xml string

    if not inventory.is_ok:
        print(inventory.status_code)
        print(inventory.reason)
        print('Response Error exiting without running script')
        return

    inventory.populate_inventory_data()  # parse the xml and put data in python dictionaries
    # inventory_name_id_dict, inventory_name_circuit_id_dict, services
    inventory.post_inventory_to_cogeco(only_new = False)  # make POST request to COGECO_TEST

    print()
    print(f'Number of circuits fetched {len(inventory.inventory_name_id_dict.keys())}')  # Shows number of items populated in dict
    print(f'POSTED {inventory.post_counter} GROUPS!')  # shows number of groups posted

    inventory.everything_file = open(EVERYTHING_LOG_FILE_NAME, 'w') # todo 24 jun
    # todo 10jun write to POST everything LOG FILE
    for service_name in inventory.services:
        inventory.everything_file.write(f'{service_name}\n')
    inventory.everything_file.write(f'posted {len(inventory.new_services)} new groups as listed above')

def post_new(inventory):
    inventory.my_file = open(LOG_FILE_NAME, 'w')
    inventory.get_inventory_xml()  # run the get function to get inventory ASGC xml string

    if not inventory.is_ok:
        print(inventory.status_code)
        print(inventory.reason)
        print('Response Err(f'posted {len(inventory.new_services)} new groups as listed above')
    print(f'posted {len(inventory.new_services)} new groups as listed above')

or exiting without running script')
        return

    inventory.populate_inventory_data()  # parse the xml and put data in python dictionaries
    # May - 4 BEGIN
    inventory.get_cogeco_xml()  # so that we can compare to find new items in inventory ASGC; 5/4/2021

    # 1) parse xml and create a set of all names [set has fast search like dict]
    # 2) compare cogeco names with ASGC names and create a list with ONLY NEW NAMES
    inventory.populate_new_inventory_data()

    # Make post request with ONLY NEW NAMES LIST
    inventory.post_inventory_to_cogeco(only_new=True)  # make POST request to COGECO_TEST

    for service_name in inventory.new_services:
        inventory.my_file.write(f'{service_name}\n')
        print(service_name)
        # TODO 4, test script output to file instead of print
    inventory.my_file.write
def delete_cogeco(inventory):
    inventory.get_inventory_xml()  # run the get function to get inventory ASGC xml string

    if not inventory.is_ok:
        print(inventory.status_code)
        print(inventory.reason)
        print('Response Error exiting without running script')
        return

    inventory.populate_inventory_data()  # parse the xml and put data in python dictionaries
    inventory.get_cogeco_xml()  # so that we can compare to find new items in inventory ASGC; 5/4/2021
    # 1) parse xml and create a set of all names [set has fast search like dict]
    # 2) compare cogeco names with ASGC names and create a list with ONLY NEW NAMES
    inventory.populate_new_inventory_data(create_new_name_list=False)
    inventory.del_cogeco_after_inventory_del()


if __name__ == '__main__':

    print(f'script started at {datetime.datetime.now()}')
    inventory = InventoryNewToCogeco()  # create an object of this class

    post_new(inventory)  #TODO: Value only group id is being fetched, not circuit ID name
    delete_cogeco(inventory)  # TODO: delete is running twice, need to fix ALSO configure email reporting functionality
    # post_everything(inventory)  #This will post everything and overwrite existing ones
    print(f'script finished at {datetime.datetime.now()}')
