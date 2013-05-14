import numpy
from pysovo import contacts
import pysovo as ps
from astropysics.coords.coordsys import FK5Coordinates
from astropysics.obstools import Site
import LofarCtl
import datetime
import pytz
import astropysics
import logging



##### ##### #####
##### Setting the alert mechanism

### Defining the function that formats the email body
def format_email_alert(target_coords, target_name, comment, action, requester):
    ## Making sure that the coordinates are a proper FK5Coordinates instance
    assert isinstance(target_coords, FK5Coordinates)
    ra_str = target_coords.ra.getHmsStr(canonical=True)
    dec_str = target_coords.dec.getDmsStr(canonical=True)
    alert_text = "".join(["Target=    ", target_name, "\n"
                "J2000RA=   ", ra_str, "\n",
                "J2000Dec=  ", dec_str, "\n",
                "Timing=    ", "ASAP", "\n",
                "Duration=  ", "01.00", "\n",
                "Requester= ", requester.name, "\n",
                "Comment=  ", comment, "\n",
                "Action=  ", action, "\n"
                ])
    return alert_text

def AltAzPosition(self, sources, time_up):
    """AltAzPosition(sources, time_up)
    Returns the altitude and azimuth in degrees of a list of sources at the
    observatory location.
    
    sources (list(FK5Coordinates)): A list of source coordinates
    time_up (datetime): A datetime.datetime object of the time to compute the
        elevation for.
    """
    pos = numpy.empty((2,self.nsources))
    for i,s in enumerate(cal.sources):
        coord = self.apparentCoordinates(s, time_up)[0]
        pos[:,i] = coord.alt.degrees, coord.az
    return elevation

### Defining the function that processes the request
def internal_request_mechanism(self, target_coords, target_name, duration, debug=True):
    """internal_request_mechanism(self, target_coords, target_name, duration, debug=True)
    This function processes the observation request. It determines the station availability,
    determines the observation strategy and launches the observing script.

    station (Observatory): An Observatory instance providing the details about the
        LOFAR station that is requested to be triggered.
    target_coords (FK5Coordinates): An FK5Coordinates instance providing the
        coordinates of the target of the trigger.
    target_name (str): A string providing a unique identifier for the trigger.
    duration (int): Duration of the observation in seconds.
    debug (bool): If true, will execute a dry run version of the script.

    Returns:
    status (int): An integer providing the execution status of the function.
        -1: station not available
        -2: station already triggered
        0: success
        1: failure
        2: source not visible
        3: no calibrator
    msg (str): A message containing information about the execution of the function.
        This is generally what will be contained in the body of a notification email.
    """
    ##### #####
    ##### Determining if the station is available
    status, msg = self.check_available()
    ## log - start
    logging.info( "internal_request_mechanism | availability status: {}".format(status) )
    ## log - end
    ## Station not available
    if status == 1:
        status = -status
        return status,  alert_message
    ## Station already triggered
    elif status == 2:
        status = -status
        return status,  alert_message
    
    ##### #####
    ##### Determining the source elevation
    duration = int(duration)
    time_start = datetime.datetime.now(pytz.utc)
    time_end = astropysics.obstools.jd_to_calendar(astropysics.obstools.calendar_to_jd(time_start)+duration)
    ## log - start
    logging.debug( "internal_request_mechanism | duration: {}, time_start: {}, time_end: {}".format(duration, time_start, time_end) )
    ## log - end

    if not self.on_sky(target_coords, time_start):
        print( "The source is not visible." )
        status = 2
        msg = "Target not visible at the moment from the facility."
        ## log - start
        logging.info( "internal_request_mechanism | visibility status: {}, msg: {}".format(status, msg) )
        ## log - end
        return status, msg
    
    ##### #####
    ##### Determining the calibration source to use
    cal = LofarCtl.Calibrator()

    separation = cal.Separation(target_coords)
    elevation_start = self.Elevation(station, time_start)
    elevation_end = self.Elevation(station, time_end)
    inds = (elevation_start > 10) * (elevation_end > 10)
    ## log - start
    logging.debug( "internal_request_mechanism | calibrator separation: {}, elevation_start: {}, elevation_end: {}".format(separation, elevation_start, elevation_end) )
    ## log - end

    ## If no calibrator is available, the function will return abruptly with an error status and message
    if inds.any():
        calibrator_id = (separation*inds).argmax()
        print( "Choosing calibrator {0} at {1:.3f} degrees from the source.".format(cal.names[calibrator_id], separation[calibrator_id]) )
        ## log - start
        logging.debug( "internal_request_mechanism | choosing calibrator {} at {:.3f} degrees from the source.".format(cal.names[calibrator_id], separation[calibrator_id]) )
        ## log - end
    else:
        print( "No calibrator could be set." )
        status = 3
        msg = "No calibrator could be set."
        ## log - start
        logging.info( "internal_request_mechanism | calibrator status: {}, msg: {}".format(status, msg) )
        ## log - end
        return status, msg

    ##### #####
    ##### Defining the observational parameters
    antennaset = "HBA_DUAL"
    rcumode = 5

    ##### #####
    ##### Extracting the coordinates from the target_coords object
    ra = target_coords.ra.degrees
    dec = target_coords.dec.degrees
    ra_ref = cal.sources[calibrator_id].ra.degrees
    dec_ref = cal.sources[calibrator_id].dec.degrees
    coordsys = 'J2000'
    ## log - start
    logging.debug( "internal_request_mechanism | antennaset {}, rcumode {}".format(antennaset, rcumode) )
    logging.debug( "internal_request_mechanism | ra {}, dec {}".format(ra, dec) )
    logging.debug( "internal_request_mechanism | ra_ref {}, dec_ref {}".format(ra_ref, dec_ref) )
    ## log - end

    ##### #####
    ##### Setting up the station control script
    ### Creating the Obs instance
    obs = LofarCtl.Observation(duration=duration, antennaset=antennaset, rcumode=rcumode)

    ### We generate the list of subbands required for the Beam setup
    ### There are 4 machines recording the data so we use the scheme:
    ###     machine01 -> science beamlets 0-30, calibrator beamlets 0-29
    ###     machine02 -> science beamlets 31-61, calibrator beamlets 30-59
    ###     machine03 -> science beamlets 62-92, calibrator beamlets 60-89
    ###     machine04 -> science beamlets 93-123, calibrator beamlets 90-119
    ### This allows to record almost exactly the same bandwidth on each machine so if one fails the whole observation is not lost
    first_subs = 220
    science_subs = []
    calibrator_subs = []
    for i in xrange(4):
        subs = numpy.arange(first_subs+i*31, first_subs+(i+1)*31)
        science_subs.append( subs )
        calibrator_subs.append( subs[:-1] )

    ### Creating the science and reference beams
    for i in xrange(4):
        obs.Add_beam(science_subs[i], ra, dec, coordsys=coordsys, inradians=False)
        obs.Add_beam(calibrator_subs[i], ra_ref, dec_ref, coordsys=coordsys, inradians=False)

    ##### #####
    ##### Calling the triggering script
    triggering_status = LofarCtl.scripts.fast_triggering.trigger_lofarintl(obs.obsctl, target_name, duration, debug=debug)
    
    ##### #####
    ##### Preparing the output
    ### Status (0: good (debug=False), 1: failed (debug=True), 2: source not visible, 3: no calibrator)
    if debug:
        status = 1
        msg = "No observation request sent; debug mode."
    else:
        status = 0
        msg = "Observation request sent succesfully."
    
    msg = "\n    Here is the setup we used:\n"
    msg += "        antennaset: {0}\n".format(antennaset)
    msg += "        rcumode: {0}\n".format(rcumode)
    msg += "        calibrator: {0}\n".format(cal.names[calibrator_id])
    msg += "        duration: {0}".format(duration)
    
    ## log - start
    logging.info( "internal_request_mechanism | observation status {}".format(status) )
    ## log - end

    return status, msg

### Defining the function that gathers the trigger request information and pass it on to the station GRB script
def request_observation(self, target_coords, target_name, duration, debug=True):
    """request_observation(self, target_coords, target_name, duration, debug=True)
    
    >>> status, alert_message = request_observation(station, target_coords, target_name, duration, debug=True)
    
    status:
        -1: station not available
        -2: station already triggered
        0: success
        1: failure
        2: source not visible
        3: no calibrator
    """
    ## Triggering the observation request
    status, msg = self.internal_request_mechanism(target_coords, target_name, duration, debug=debug)
    alert_message = msg

    return status,  alert_message





##### ##### #####
##### Setting up the observatories

##### Defining a subclass of Observatory
class LofarIntl(Site):
    def __init__(self, lat, long, alt=0., tz=None, name=None, target_min_elevation=0.):
        super(LofarIntl, self ).__init__(lat, long, alt=alt, tz=tz, name=name)
        self.target_min_elevation = target_min_elevation
        ## Attaching the request_observation method
        self.request_observation = request_observation
        ## Attaching the internal_request_mechanism method
        self.internal_request_mechanism = internal_request_mechanism

    def notification_email(self, alert_message, local_config, subject):
        ps.comms.email.send_email(account=local_config.email_account, recipient_addresses=self.email_address, subject=subject, body_text=alert_message, verbose=True)


##### Chilbolton
### Defining the observatory setup
chilbolton = LofarIntl(51.145762, -1.428495, alt=78., target_min_elevation=10., tz=0, name="LOFAR-UK (Chilbolton station)")

### Attributes specific to this particular site:
chilbolton.default_action = "NONE"
chilbolton.default_requester = ps.contacts['rene']
### Function that returns True if the facility is available, otherwise False
chilbolton.check_available = LofarCtl.scripts.fast_triggering.check_available_chilbolton


##### Nancay
### Defining the observatory setup
nancay = LofarIntl('+47:23:00', '02:12:00', alt=10., target_min_elevation=10., tz=1, name="LOFAR-FR (Nancay station)")

### Attributes specific to this particular site:
nancay.default_action = "NONE"
nancay.default_requester = ps.contacts['rene']
### Function that returns True if the facility is available, otherwise False
nancay.check_available = LofarCtl.scripts.fast_triggering.check_available_nancay



