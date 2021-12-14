# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import os

import pytest

from wazuh_testing.tools import WAZUH_PATH, WAZUH_LOGS_PATH
from wazuh_testing.tools.file import read_yaml
from wazuh_testing.tools.monitoring import HostMonitor
from wazuh_testing.tools.system import HostManager


# Hosts
testinfra_hosts = ["wazuh-manager", "wazuh-agent1"]

inventory_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'provisioning', 'basic_environment', 'inventory.yml')
host_manager = HostManager(inventory_path)
local_path = os.path.dirname(os.path.abspath(__file__))
messages_path = os.path.join(local_path, 'data/messages.yml')
tmp_path = os.path.join(local_path, 'tmp')
agent_conf_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..',
                                'provisioning', 'basic_environment', 'roles', 'agent-role', 'files', 'ossec.conf')
manager_conf_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..',
                                'provisioning', 'basic_environment', 'roles', 'manager-role', 'files', 'ossec.conf')
test_cases_yaml = read_yaml(os.path.join(local_path, 'data/test_enrollment_cases.yml'))

network = {}


# Remove the agent once the test has finished
@pytest.fixture(scope='function')
def clean_environment():
    yield
    agent_id = host_manager.run_command('wazuh-manager', f'cut -c 1-3 {WAZUH_PATH}/etc/client.keys')
    host_manager.get_host('wazuh-manager').ansible("command", f'{WAZUH_PATH}/bin/manage_agents -r {agent_id}',
                                                  check=False)
    host_manager.control_service(host='wazuh-agent1', service='wazuh', state="stopped")
    host_manager.clear_file(host='wazuh-agent1', file_path=os.path.join(WAZUH_PATH, 'etc', 'client.keys'))


@pytest.mark.parametrize('test_case', [cases for cases in test_cases_yaml], ids = [cases['name'] for cases in test_cases_yaml])
def test_agent_enrollment(test_case, get_ip_directions, configure_network, modify_ip_address_conf, clean_environment):
    """Check agent enrollment process works as expected. An agent pointing to a worker should be able to register itself
    into the manager by starting Wazuh-agent process."""
    # Clean ossec.log and cluster.log
    host_manager.clear_file(host='wazuh-manager', file_path=os.path.join(WAZUH_LOGS_PATH, 'ossec.log'))
    host_manager.clear_file(host='wazuh-agent1', file_path=os.path.join(WAZUH_LOGS_PATH, 'ossec.log'))

    ## Start the agent enrollment process by restarting the wazuh-agent
    host_manager.control_service(host='wazuh-manager', service='wazuh', state="restarted")
    host_manager.get_host('wazuh-agent1').ansible('command', f'service wazuh-agent restart', check=False)

    # Run the callback checks for the ossec.log
    HostMonitor(inventory_path=inventory_path,
                messages_path=messages_path,
                tmp_path=tmp_path).run()

    # Make sure the agent's and manager's client.keys have the same keys
    agent_client_keys =  host_manager.get_file_content('wazuh-agent1', os.path.join(WAZUH_PATH, 'etc', 'client.keys'))
    manager_client_keys =  host_manager.get_file_content('wazuh-agent1', os.path.join(WAZUH_PATH, 'etc', 'client.keys'))

    assert agent_client_keys == manager_client_keys

    # Check if the agent is active
    agent_id = host_manager.run_command('wazuh-manager', f'cut -c 1-3 {WAZUH_PATH}/etc/client.keys')
    assert host_manager.run_command('wazuh-manager', f'{WAZUH_PATH}/bin/agent_control -i {agent_id} | grep Active')

# IPV6 fixtures
@pytest.fixture(scope='module')
def get_ip_directions():
    global network

    manager_network = host_manager.get_host_ip('wazuh-manager')
    agent_network = host_manager.get_host_ip('wazuh-agent1')

    network['manager_network'] = manager_network
    network['agent_network'] = agent_network


@pytest.fixture(scope='function')
def configure_network(test_case):


    for configuration in test_case['test_case']:
        # Manager network configuration
        if 'ipv6' in configuration['manager_network']:
            host_manager.run_command('wazuh-manager', 'ip -4 addr flush dev eth0')
        elif 'ipv4' in configuration['manager_network']:
            host_manager.run_command('wazuh-manager', 'ip -6 addr flush dev eth0')

        # Agent network configuration
        if 'ipv6' in configuration['agent_network']:
            host_manager.run_command('wazuh-agent1', 'ip -4 addr flush dev eth0')

        elif 'ipv4' in configuration['agent_network']:
            host_manager.run_command('wazuh-agent1', 'ip -6 addr flush dev eth0')

    yield

    for configuration in test_case['test_case']:
        # Restore manager network configuration
        if 'ipv6' in configuration['manager_network']:
            host_manager.run_command('wazuh-manager', f"ip addr add {network['manager_network'][0]} dev eth0")
            host_manager.run_command('wazuh-manager', 'ip route add 172.24.27.0/24 via 0.0.0.0 dev eth0')
        elif 'ipv4' in configuration['manager_network']:
            host_manager.run_command('wazuh-manager', f"ip addr add {network['manager_network'][1]} dev eth0")

        # Restore agent network configuration
        if 'ipv6' in configuration['agent_network']:
            host_manager.run_command('wazuh-agent1', f"ip addr add {network['agent_network'][0]} dev eth0")
            host_manager.run_command('wazuh-agent1', 'ip route add 172.24.27.0/24 via 0.0.0.0 dev eth0')
        elif 'ipv4' in configuration['agent_network']:
            host_manager.run_command('wazuh-agent1', f"ip addr add {network['agent_network'][1]} dev eth0")


@pytest.fixture(scope='function')
def modify_ip_address_conf(test_case):

    with open(agent_conf_file, 'r') as file:
	    old_configuration = file.read()

    with open(messages_path, 'r') as file:
        messages = file.read()

    with open(manager_conf_file, 'r') as file:
	    old_manager_configuration = file.read()

    for configuration in test_case['test_case']:
        if 'yes' in configuration['ipv6_enabled']:
            new_manager_configuration = old_manager_configuration.replace('<ipv6>no</ipv6>','<ipv6>yes</ipv6>')
            host_manager.modify_file_content(host='wazuh-manager', path='/var/ossec/etc/ossec.conf', content=new_manager_configuration)

        if 'ipv4' in configuration['ip_type']:
            new_configuration = old_configuration.replace('<address>MANAGER_IP</address>',f"<address>{network['manager_network'][0]}</address>")
            host_manager.modify_file_content(host='wazuh-agent1', path='/var/ossec/etc/ossec.conf', content=new_configuration)
            messages_with_ip = messages.replace('MANAGER_IP', f"{network['manager_network'][0]}")
        elif 'ipv6' in  configuration['ip_type']:
            new_configuration = old_configuration.replace('<address>MANAGER_IP</address>',f"<address>{network['manager_network'][1]}</address>")
            host_manager.modify_file_content(host='wazuh-agent1', path='/var/ossec/etc/ossec.conf', content=new_configuration)
            messages_with_ip = messages.replace('MANAGER_IP', f"{network['manager_network'][1]}")
        elif 'dns' in configuration['ip_type']:
            new_configuration = old_configuration.replace('<address>MANAGER_IP</address>',f"<address>wazuh-manager</address>")
            host_manager.modify_file_content(host='wazuh-agent1', path='/var/ossec/etc/ossec.conf', content=new_configuration)
            if 'yes' in configuration['ipv6_enabled']:
                if 'ipv4' in configuration['manager_network'] or 'ipv4' in configuration['agent_network']:
                    messages_with_ip = messages.replace('MANAGER_IP', f"wazuh-manager/{network['manager_network'][0]}")
                else:
                    messages_with_ip = messages.replace('MANAGER_IP', f"wazuh-manager/{network['manager_network'][1]}")
            else:
                messages_with_ip = messages.replace('MANAGER_IP', f"wazuh-manager/{network['manager_network'][0]}")

        if 'ipv4' in configuration['ip_type']:
            messages_with_ip = messages_with_ip.replace('AGENT_IP', f"{network['agent_network'][0]}")
        elif 'ipv6' in configuration['ip_type']:
            messages_with_ip = messages_with_ip.replace('AGENT_IP', f"{network['agent_network'][1]}")
        elif 'dns' in configuration['ip_type']:
            if 'yes' in configuration['ipv6_enabled']:
                if 'ipv4' in configuration['agent_network']:
                    messages_with_ip = messages_with_ip.replace('AGENT_IP', f"{network['agent_network'][0]}")
                else:
                    messages_with_ip = messages_with_ip.replace('AGENT_IP', f"{network['agent_network'][1]}")
            else:
                messages_with_ip = messages_with_ip.replace('AGENT_IP', f"{network['agent_network'][0]}")

    with open(messages_path, 'w') as file:
            file.write(messages_with_ip)

    yield

    with open(messages_path, 'w') as file:
            file.write(messages)
