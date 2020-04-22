import pytest
from wazuh_testing.tools import LOG_FILE_PATH
from wazuh_testing.tools.monitoring import FileMonitor
from wazuh_testing.cluster import callback_detect_worker_connected, callback_detect_master_serving, cluster_msg_build

@pytest.fixture(scope='function')
def wait_for_agentd_startup(request):
    """Wait until agentd has begun"""
    def callback_agentd_startup(line):
        if 'Accepting connections on port 1515' in line:
            return line
        return None

    log_monitor = FileMonitor(LOG_FILE_PATH)
    log_monitor.start(timeout=30, callback=callback_agentd_startup)
    

