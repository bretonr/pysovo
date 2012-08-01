import pysovo as ps 
import pysovo.email as email
import pysovo.address_book as address_book 
from astropysics.coords.coordsys import FK5Coordinates 
from observatory import Observatory
from LofarCtl.scripts import fast_triggering



##### ##### #####
##### Setting up the observatory

### Defining the observatory setup
chilbolton = Observatory(lat = 51.145762,
                  long = -1.428495,
                  site_altitude = 78,        
                  target_min_elevation = 20, #TO DO: Find out what this should actually be
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
chilbolton.check_available = fast_triggering.check_available



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
##### Setting the script that does the triggering work

### Defining the function that gathers the trigger request information and pass it on to the Chilbolton GRB script
def request_chilbolton_observation(target_coords, alert_type, voevent, local_config, duration, debug=True, action=None, requester=None):
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
    else:
        target_name = "4PISKY"
        comment = "Manual trigger"+debug_msg
        subject = "Manual Chilbolton fast triggering"+debug_msg
    
    ## Attempts to run the triggering script if the facility is available
    if chilbolton.check_available():
        status, msg = fast_triggering.trigger_grb_chilbolton(chilbolton, target_coords, target_name, duration, debug=debug)
    else:
        status = 0
        msg = "    Station not available at the requested time!\n"
    
    if msg is not None:
        comment += "\n" + msg

    ## Formatting the notification email body
    alert_message = format_chilbolton_email_alert(target_coords, target_name, comment, action, requester)

    ## Send the notification email
    chilbolton.internal_request_mechanism(alert_message, local_config, subject=subject)
    return status,  alert_message

### Copying the function to a generic name
chilbolton.request_observation = request_chilbolton_observation





