from time import sleep
import logging
from wazuh_testing.qa_ctl.provisioning.ansible.AnsibleInstance import AnsibleInstance
from wazuh_testing.qa_ctl.provisioning.ansible.AnsibleInventory import AnsibleInventory
from wazuh_testing.qa_ctl.provisioning.wazuh_deployment.LocalPackage import LocalPackage
from wazuh_testing.qa_ctl.provisioning.wazuh_deployment.WazuhSources import WazuhSources
from wazuh_testing.qa_ctl.provisioning.wazuh_deployment.AgentDeployment import AgentDeployment
from wazuh_testing.qa_ctl.provisioning.wazuh_deployment.ManagerDeployment import ManagerDeployment
from wazuh_testing.qa_ctl.provisioning.qa_framework.QAFramework import QAFramework


class QAProvisioning():
    """Class to control different options and instances to provisioning with Wazuh and QA Framework.

    Attributes:
        provision_info (dict): Dict with all the info needed coming from config file.
        instances_list (list): List with every instance (each host) needed to build the ansible inventory.
        group_dict (dict): Dict with groups and every host belonging to them.
        host_list (list): List with every host given in config file.
        inventory_file_path (string): Path of the inventory file generated.
        wazuh_installation_paths (dict): Dict indicating the Wazuh installation paths for every host.

    Args:
        provision_info (dict): Dict with all the info needed coming from config file.
        instances_list (list): List with every instance (each host) needed to build the ansible inventory.
        group_dict (dict): Dict with groups and every host belonging to them.
        host_list (list): List with every host given in config file.
        inventory_file_path (string): Path of the inventory file generated.
        wazuh_installation_paths (dict): Dict indicating the Wazuh installation paths for every host.
    """
    def __init__(self, provision_info):
        self.provision_info = provision_info
        self.instances_list = []
        self.group_dict = {}
        self.host_list = []
        self.inventory_file_path = None
        self.wazuh_installation_paths = {}

    def __read_ansible_instance(self, host_info):
        """Read every host info and generate the AnsibleInstance object.

        Attributes:
            host_info (dict): Dict with the host info needed coming from config file.

        Returns:
            instance (AnsibleInstance): Contains the AnsibleInstance for a given host.
        """
        extra_vars = None if 'host_vars' not in host_info else host_info['host_vars']
        private_key_path = None if 'local_private_key_file_path' not in host_info \
                                   else host_info['local_private_key_file_path']
        instance = AnsibleInstance(host=host_info['host'], host_vars=extra_vars,
                                   connection_method=host_info['connection_method'],
                                   connection_port=host_info['connection_port'], connection_user=host_info['user'],
                                   connection_user_password=host_info['password'],
                                   ssh_private_key_file_path=private_key_path,
                                   ansible_python_interpreter=host_info['ansible_python_interpreter'])
        return instance

    def process_inventory_data(self):
        """Process config file info to generate the ansible inventory file."""
        for root_key, root_value in self.provision_info.items():
            if root_key == "hosts":
                for _, host_value in root_value.items():
                    for module_key, module_value in host_value.items():
                        if module_key == "host_info":
                            current_host = module_value['host']
                            if current_host:
                                self.instances_list.append(self.__read_ansible_instance(module_value))
            elif root_key == "groups":
                self.group_dict.update(self.provision_info[root_key])

        inventory_instance = AnsibleInventory(ansible_instances=self.instances_list,
                                              ansible_groups=self.group_dict)
        self.inventory_file_path = inventory_instance.inventory_file_path

    def process_deployment_data(self):
        """Process config file info to generate all the tasks needed for deploy Wazuh"""
        for _, host_value in self.provision_info['hosts'].items():
            current_host = host_value['host_info']['host']
            if 'wazuh_deployment' in host_value:
                deploy_info = host_value['wazuh_deployment']
                health_check = True if 'health_check' not in host_value['wazuh_deployment'] \
                                       else host_value['wazuh_deployment']['health_check']
                install_target = None if 'target' not in deploy_info else deploy_info['target']
                install_type = None if 'type' not in deploy_info else deploy_info['type']
                installation_files_path = None if 'installation_files_path' not in deploy_info \
                                                  else deploy_info['installation_files_path']
                wazuh_install_path = None if 'wazuh_install_path' not in deploy_info \
                                             else deploy_info['wazuh_install_path']
                wazuh_branch = 'master' if 'wazuh_branch' not in deploy_info else deploy_info['wazuh_branch']
                local_package_path = None if 'local_package_path' not in deploy_info \
                                             else deploy_info['local_package_path']
                manager_ip = None if 'manager_ip' not in deploy_info else deploy_info['manager_ip']

                installation_files_parameters = {'wazuh_target': install_target}

                if installation_files_path:
                    installation_files_parameters['installation_files_path'] = installation_files_path
                if wazuh_install_path:
                    installation_files_parameters['wazuh_install_path'] = wazuh_install_path

                if install_type == "sources":
                    installation_files_parameters['wazuh_branch'] = wazuh_branch
                    installation_instance = WazuhSources(**installation_files_parameters)
                if install_type == "package":
                    installation_files_parameters['local_package_path'] = local_package_path
                    installation_instance = LocalPackage(**installation_files_parameters)

                remote_files_path = installation_instance.download_installation_files(self.inventory_file_path,
                                                                                      hosts=current_host)

                if install_target == "agent":
                    deployment_instance = AgentDeployment(remote_files_path,
                                                          inventory_file_path=self.inventory_file_path,
                                                          install_mode=install_type, hosts=current_host,
                                                          server_ip=manager_ip)
                if install_target == "manager":
                    deployment_instance = ManagerDeployment(remote_files_path,
                                                            inventory_file_path=self.inventory_file_path,
                                                            install_mode=install_type, hosts=current_host)

                deployment_instance.install()

                if health_check:
                    logging.info('Waiting for Wazuh installation')
                    sleep(60)
                    logging.info('Performing health check')
                    deployment_instance.health_check()
                else:
                    logging.warning('Health check not performed')

                self.wazuh_installation_paths[deployment_instance.hosts] = deployment_instance.install_dir_path

            if 'qa_framework' in host_value:
                qa_framework_info = host_value['qa_framework']
                wazuh_qa_branch = None if 'wazuh_qa_branch' not in qa_framework_info \
                                          else qa_framework_info['wazuh_qa_branch']

                qa_instance = QAFramework(qa_branch=wazuh_qa_branch)
                qa_instance.download_qa_repository(inventory_file_path=self.inventory_file_path, hosts=current_host)
                qa_instance.install_dependencies(inventory_file_path=self.inventory_file_path, hosts=current_host)
                qa_instance.install_framework(inventory_file_path=self.inventory_file_path, hosts=current_host)
