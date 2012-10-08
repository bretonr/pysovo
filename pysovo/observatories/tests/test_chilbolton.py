import unittest
from VOEventLib import VOEvent as voe

import pysovo
from pysovo.observatories import chilbolton

import test_data

import datetime, pytz
import astropysics

###
debug = True

class TestChilboltonModule(unittest.TestCase):
    def setUp(self):
        chilbolton.default_action = "UNITTEST"
        v = voe.VOEvent(version="2.0")
        v.set_ivorn("ivo://nasa.gsfc.gcn/SWIFT#BAT_GRB_Pos_517234-259")
        self.voevent = v
        self.coords = test_data.arbitrary_eqpos
        self.local_config =  pysovo.LocalConfig(email_account=pysovo.email.load_account_settings_from_file())

    def test_trigger_on_sky(self):
        self.coords = test_data.equatorial_on_sky_chilbolton
        status, observation_text = chilbolton.request_observation(self.coords, "swift_grb", self.voevent, self.local_config, 120, debug=debug)
        print("")
        print("Sample Chilbolton request body text (source on sky):")
        print(observation_text)

    def test_trigger_off_sky(self):
        self.coords = test_data.equatorial_off_sky_chilbolton
        status, observation_text = chilbolton.request_observation(self.coords, "swift_grb", self.voevent, self.local_config, 120, debug=debug)
        print("")
        print("Sample Chilbolton request body text (source off sky):")
        print(observation_text)


if __name__ == '__main__':
    unittest.main()

