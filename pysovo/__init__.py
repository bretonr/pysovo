from __future__ import absolute_import
import os
import json
import logging
import sys
logger = logging.getLogger(__name__)

config_folder = os.path.join(os.environ['HOME'], '.pysovo')
default_email_config_file = os.path.join(config_folder, "email_acc")

import pysovo.comms
import pysovo.utils
import pysovo.observatories
import pysovo.notify

try:
    contacts_file = os.path.join(config_folder, 'contacts.json')
    print( contacts_file )
    with open(contacts_file) as f:
        contacts = json.load(f)
    logger.debug('Contacts loaded from ' + contacts_file)
except Exception as e:
    logger.warn("Could not load contacts file; reason:\n" + str(e))
    contacts = {}







