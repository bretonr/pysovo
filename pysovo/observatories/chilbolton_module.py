import pysovo as ps 
import pysovo.email as email
import pysovo.address_book as address_book 
from astropysics.coords.coordsys import FK5Coordinates 
from observatory import Observatory
import LofarCtl
import datetime
import astropysics



##### ##### #####
##### Setting up the observatory

### Defining the observatory setup
chilbolton = Observatory(lat = 51.145762,
                  long = -1.428495,
                  site_altitude = 78,        
                  target_min_elevation = 10, #TO DO: Find out what this should actually be
                  tz = 0,
                  name = "LOFAR-UK (Chilbolton station)",
                  short_name = "Chilbolton",
                  email_address = [contact.email for contact in ps.address_book.chilbolton_list]
                  )

### Attributes specific to this particular site:
chilbolton.default_action = "NONE"
chilbolton.default_requester = ps.address_book.rene

### Function that returns True if the facility is available, otherwise False
#chilbolton.check_available = lambda : False
chilbolton.check_available = LofarCtl.scripts.fast_triggering.check_available_chilbolton



##### ##### #####
##### Setting the alert mechanism

### Defining the alert notification script
def notification_email(alert_message, local_config, subject):
    ps.email.send_email(account=local_config.email_account, recipient_addresses=chilbolton.email_address, subject=subject, body_text=alert_message, verbose=True)

chilbolton.internal_request_mechanism = notification_email

### Defining the function that formats the email body
def format_chilbolton_email_alert(target_coords, target_name, comment, action, requester):
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



##### ##### #####
#####
def process_observation(station, target_coords, target_name, duration, debug=True):
    """process_observation(station, target_coords, target_name, duration, debug=True)
    This function processes the observation request. It determines the station availability,
    determines the observation strategy and launches the observing script.

    station (Observatory): An Observatory instance providing the details about the
        LOFAR station that is requested to be triggered. For now, only Chilbolton.
    target_coords (FK5Coordinates): An FK5Coordinates instance providing the
        coordinates of the target of the trigger.
    target_name (str): A string providing a unique identifier for the trigger.
    duration (int): Duration of the observation in seconds.
    debug (bool): If true, will execute a dry run version of the script.

    Returns:
    status (int): An integer providing the execution status of the function.
        0: Success
        1: Failure (debug=True)
        2: Source not visible
        3: No calibrator
    msg (str): A message containing information about the execution of the function.
        This is generally what will be contained in the body of a notification email.
    """
    duration = int(duration)
    time_start = datetime.datetime.utcnow()
    time_end = astropysics.obstools.jd_to_calendar(astropysics.obstools.calendar_to_jd(time_start)+1./24)
    
    ##### #####
    ##### Determining the source elevation
    if not station.on_sky(target_coords, time_start):
        print( "The source is not visible." )
        status = 2
        msg = "    The source is not visible at the moment from the observatory!"
        return status, msg
    
    ##### #####
    ##### Determining the calibration source to use
    cal = LofarCtl.Calibrator()

    separation = cal.Separation(target_coords)
    elevation_start = cal.Elevation(station, time_start)
    elevation_end = cal.Elevation(station, time_end)
    inds = (elevation_start > 10) * (elevation_end > 10)

    ## If no calibrator is available, the function will return abruptly with an error status and message
    if inds.any():
        calibrator_id = (separation*inds).argmax()
        print( "Choosing calibrator {0} at {1:.3f} degrees from the source.".format(cal.names[calibrator_id], separation[calibrator_id]) )
    else:
        print( "No calibrator is available." )
        status = 3
        msg = "    No calibrator could be set!"
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
    triggering_status = LofarCtl.scripts.fast_triggering.trigger_grb_chilbolton(obs.obsctl, target_name, duration, debug=debug)
    
    ##### #####
    ##### Preparing the output
    ### Status (0: good (debug=False), 1: failed (debug=True), 2: source not visible, 3: no calibrator)
    if debug:
        status = 1
    else:
        status = 0
    
    msg = "    Here is the setup we used:\n"
    msg += "        antennaset: {0}\n".format(antennaset)
    msg += "        rcumode: {0}\n".format(rcumode)
    msg += "        calibrator: {0}".format(cal.names[calibrator_id])
    
    return status, msg



##### ##### #####
##### Setting the script that does the triggering work

### Defining the function that gathers the trigger request information and pass it on to the Chilbolton GRB script
def request_chilbolton_observation(target_coords, alert_type, voevent, local_config, duration, debug=True, action=None, requester=None):
    """request_chilbolton_observation(target_coords, alert_type, voevent, local_config, duration, debug=True, action=None, requester=None)
    
    >>> status, alert_message = request_chilbolton_observation(target_coords, alert_type, voevent, local_config, duration, debug=True, action=None, requester=None)
    
    status:
        -1: station not available
        -2: station already triggered
        0: success
        1: failure
        2: source not visible
        3: no calibrator
    """
    ## Provide some default values for optional attributes
    if action is None:
        action = chilbolton.default_action
    if requester is None:
        requester = chilbolton.default_requester
    
    ## If debug mode requested, format a special message
    if debug:
        debug_msg = " (DEBUG Mode)"
    else:
        debug_msg = ""

    ## Determine the type of alert and the appropriate attribute formatting
    if alert_type == ps.alert_types.swift_grb:
        alert_id = voevent.ivorn[len("ivo://nasa.gsfc.gcn/SWIFT#BAT_GRB_Pos_"):]
        target_name = "SWIFT_"+alert_id
        comment = "Automated SWIFT ID "+alert_id+debug_msg
        subject = "Swift GRB Chilbolton fast triggering"+debug_msg
    elif alert_type == ps.alert_types.fermi_grb:
        alert_id = voevent.ivorn[len("ivo://nasa.gsfc.gcn/Fermi#GBM_Gnd_Pos_"):]
        target_name = "FERMI_"+alert_id
        comment = "Automated Fermi ID "+alert_id+debug_msg
        subject = "Fermi GRB Chilbolton fast triggering"+debug_msg
    else:
        target_name = "4PISKY"
        comment = "Manual trigger"+debug_msg
        subject = "Manual Chilbolton fast triggering"+debug_msg
    
    ## Attempts to run the triggering script if the facility is available
    chilbolton_status, msg = chilbolton.check_available()
    if chilbolton_status == 0:
        status, msg = process_observation(chilbolton, target_coords, target_name, duration, debug=debug)
    else:
        ## We make the status code negative in case of a station status failure
        status = -chilbolton_status
    
    if msg is not None:
        comment += "\n" + msg +"\n"

    ## Formatting the notification email body
    alert_message = format_chilbolton_email_alert(target_coords, target_name, comment, action, requester)

    ## Send the notification email
    chilbolton.internal_request_mechanism(alert_message, local_config, subject=subject)
    return status,  alert_message

### Copying the function to a generic name
chilbolton.request_observation = request_chilbolton_observation





