# Copyright (C) 2015-2019, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2
import os
import shutil
import subprocess
import time

import pytest

from wazuh_testing.fim import WAZUH_CONF_PATH, LOG_FILE_PATH, is_fim_scan_ended, callback_detect_end_scan
from wazuh_testing.tools import truncate_file, wait_for_condition, FileMonitor


@pytest.fixture(scope='module')
def configure_environment(request):
    # Place configuration in path
    shutil.copy(os.path.join(getattr(request.module, 'test_data_path'), 'ossec.conf'), WAZUH_CONF_PATH)
    shutil.chown(WAZUH_CONF_PATH, 'root', 'ossec')
    os.chmod(WAZUH_CONF_PATH, mode=0o660)

    # Create test directories
    test_directories = getattr(request.module, 'test_directories')
    for test_dir in test_directories:
        os.mkdir(test_dir)

    yield
    # Remove created folders
    for test_dir in test_directories:
        shutil.rmtree(test_dir)


@pytest.fixture(scope='module')
def restart_wazuh(request):
    # Reset ossec.log and start a new monitor
    truncate_file(LOG_FILE_PATH)
    file_monitor = FileMonitor(LOG_FILE_PATH)
    setattr(request.module, 'wazuh_log_monitor', file_monitor)

    # Restart Wazuh and wait for the command to end
    p = subprocess.Popen(["service", "wazuh-manager", "restart"])
    p.wait()

    # Wait for initial FIM scan to end
    file_monitor.start(timeout=60, callback=callback_detect_end_scan)

    # Add additional sleep to avoid changing system clock issues (TO BE REMOVED when syscheck has not sleeps anymore)
    time.sleep(11)