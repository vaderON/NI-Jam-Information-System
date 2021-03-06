import random
import string
import uuid

import os

import math

from models import *
from eventbrite_interactions import get_eventbrite_attendees_for_event
import datetime
from copy import deepcopy
import configuration

red = "#fc9f9f"
orange = "#fcbd00"
yellow = "#fff60a"
green = "#c4fc9f"
grey = "#969696"
blue = "#00bbff"
light_grey = "#ededed"
light_blue = "#00dbc1"


def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    Base.metadata.create_all(bind=engine, pool_recycle=25200)


def convert_to_mysql_datetime(datetime_to_convert: datetime.datetime) -> str:
    f = '%Y-%m-%d %H:%M:%S'
    return datetime_to_convert.strftime(f)


def convert_to_python_datetime(datetime_to_convert: str) -> datetime.datetime:
    f = '%Y-%m-%d %H:%M:%S'
    return datetime.datetime.strptime(datetime_to_convert, f)


def get_logged_in_user_object_from_cookie(cookie_value: str) -> LoginUser:
    found_cookie = db_session.query(LoginCookie).filter(LoginCookie.cookie_value == cookie_value).first()
    if found_cookie:
        return found_cookie.user
    return None


def add_jam(eventbrite_id, jam_name, date): # Add a new Jam, plus a series of placeholder default hidden workshops (parking, front desk and break time)
    jam = RaspberryJam(jam_id=eventbrite_id, name=jam_name, date=date) # Add the Jam row
    db_session.add(jam)
    db_session.commit()
    if configuration.verify_config_item_bool("general", "new_jam_add_default_events"):
        car_parking_workshop = db_session.query(Workshop).filter(Workshop.workshop_title == "Car Parking").first()
        car_parking_room = db_session.query(WorkshopRoom).filter(WorkshopRoom.room_name == "Car Park").first()
        car_parking = RaspberryJamWorkshop(jam_id=jam.jam_id, workshop_id=car_parking_workshop.workshop_id, workshop_room_id=car_parking_room.room_id, slot_id=0, pilot=0)
        db_session.add(car_parking) # Add car parking into slot 0

        front_desk_workshop = db_session.query(Workshop).filter(Workshop.workshop_title == "Front desk").first()
        front_desk_registration_room = db_session.query(WorkshopRoom).filter(WorkshopRoom.room_name == "Front Desk Registration").first()
        front_desk_room = db_session.query(WorkshopRoom).filter(WorkshopRoom.room_name == "Front Desk General").first()
        front_desk = RaspberryJamWorkshop(jam_id=jam.jam_id, workshop_id=front_desk_workshop.workshop_id, workshop_room_id=front_desk_registration_room.room_id, slot_id=0, pilot=0)

        db_session.add(front_desk) # Add front desk registration

        front_desk = RaspberryJamWorkshop(jam_id=jam.jam_id, workshop_id=front_desk_workshop.workshop_id, workshop_room_id=front_desk_room.room_id, slot_id=1, pilot=0)
        db_session.add(front_desk)
        front_desk = RaspberryJamWorkshop(jam_id=jam.jam_id, workshop_id=front_desk_workshop.workshop_id, workshop_room_id=front_desk_room.room_id, slot_id=2, pilot=0)
        db_session.add(front_desk)
        front_desk = RaspberryJamWorkshop(jam_id=jam.jam_id, workshop_id=front_desk_workshop.workshop_id, workshop_room_id=front_desk_room.room_id, slot_id=3, pilot=0)
        db_session.add(front_desk)
        front_desk = RaspberryJamWorkshop(jam_id=jam.jam_id, workshop_id=front_desk_workshop.workshop_id, workshop_room_id=front_desk_room.room_id, slot_id=4, pilot=0)
        db_session.add(front_desk) # Add 4th normal front desk


        break_room = db_session.query(WorkshopRoom).filter(WorkshopRoom.room_name == "Foyer (ground floor)").first()
        break_workshop = db_session.query(Workshop).filter(Workshop.workshop_title == "Break time").first()
        break_time = RaspberryJamWorkshop(jam_id=jam.jam_id, workshop_id=break_workshop.workshop_id, workshop_room_id=break_room.room_id, slot_id=3, pilot=0)
        db_session.add(break_time) # Add break time into break session


        db_session.commit()


def get_jams_in_db():
    return db_session().query(RaspberryJam).all()


def get_jams_dict():
    jams = get_jams_in_db()
    jams_list = []
    for jam in jams:
        jams_list.append({"jam_id": jam.jam_id, "name":jam.name, "date":jam.date})
    return jams_list


def add_workshop(workshop_id, workshop_title, workshop_description, workshop_limit, workshop_level, workshop_url, workshop_volunteer_requirements):

    if workshop_id or workshop_id == 0: # If workshop already exists
        workshop = db_session.query(Workshop).filter(Workshop.workshop_id == workshop_id).first()
        workshop.workshop_title = workshop_title
        workshop.workshop_description = workshop_description
        workshop.workshop_limit = workshop_limit
        workshop.workshop_level = workshop_level
        workshop.workshop_url = workshop_url
        workshop.workshop_volunteer_requirements = workshop_volunteer_requirements
    else: # If new workshop
        workshop = Workshop(workshop_title=workshop_title, workshop_description=workshop_description, workshop_limit=workshop_limit, workshop_level=workshop_level, workshop_hidden=0, workshop_url=workshop_url, workshop_volunteer_requirements=workshop_volunteer_requirements)
        db_session.add(workshop)
    db_session.commit()


def get_workshops_for_jam_old(jam_id):
    workshops = []
    for workshop in db_session.query(RaspberryJam, RaspberryJamWorkshop, Workshop).filter(RaspberryJam.jam_id == jam_id, RaspberryJamWorkshop.workshop_id == Workshop.workshop_id):
        workshops.append({"workshop_title":workshop.Workshop.workshop_title, "workshop_description":workshop.Workshop.workshop_description, "workshop_level":workshop.Workshop.workshop_level, "workshop_time":workshop.RaspberryJamWorkshop.workshop_time_slot})
    return workshops


def update_attendees_from_eventbrite(event_id):
    attendees = get_eventbrite_attendees_for_event(event_id)
    for attendee in attendees["attendees"]:

        found_attendee = db_session.query(Attendee).filter(Attendee.attendee_id == attendee["id"]).first()

        if attendee["refunded"] == True:
            if found_attendee:
                db_session.delete(found_attendee)
            continue

        try:
            school = attendee["answers"][2]["answer"]
        except KeyError:
            school = None
        if found_attendee:
            new_attendee = found_attendee
        else:
            new_attendee = Attendee()

        new_attendee.attendee_id = attendee["id"],
        new_attendee.first_name = attendee["profile"]["first_name"],
        new_attendee.surname = attendee["profile"]["last_name"],
        new_attendee.age = attendee["profile"].get("age"),
        new_attendee.email_address = "Unknown",
        new_attendee.gender = attendee["profile"]["gender"],
        new_attendee.town = attendee["answers"][0]["answer"],
        new_attendee.experience_level = str(attendee["answers"][1]["answer"]).split()[0],
        new_attendee.school = school,
        new_attendee.order_id = attendee["order_id"],
        new_attendee.ticket_type = attendee["ticket_class_name"]
        new_attendee.jam_id = int(event_id)
        new_attendee.checked_in = attendee["checked_in"]

        # 4 available states for current_location, Checked in, Checked out, Not arrived and None.
        if new_attendee.current_location is None: # If current_location has not been set
            if attendee["checked_in"]:
                new_attendee.current_location = "Checked in"
            else:
                new_attendee.current_location = "Not arrived"
        elif new_attendee.current_location == "Not arrived" and attendee["checked_in"]:
            new_attendee.current_location = "Checked in"

        if not found_attendee:
            db_session.add(new_attendee)

    db_session.commit()


def get_attendees_in_order(order_id):
    found_attendees = db_session.query(Attendee).filter(Attendee.order_id == order_id)
    if not found_attendees:
        return None
    else:
        return found_attendees


def get_volunteers_to_select():
    volunteers = db_session.query(LoginUser)
    to_return = []
    for volunteer in volunteers:
        to_return.append((volunteer.user_id, "{} {}".format(volunteer.first_name, volunteer.surname)))
    return to_return


def get_workshops_to_select(show_archived=False):
    workshops = db_session.query(Workshop)
    if show_archived:
        return workshops
    else:
        return workshops.filter((Workshop.workshop_archived == 0) | (Workshop.workshop_archived == None))


def get_workshop_from_workshop_id(workshop_id):
    return db_session.query(Workshop).filter(Workshop.workshop_id == workshop_id).first()


def get_individual_time_slots_to_select():
    to_return = []
    for time_slots in db_session.query(WorkshopSlot):
        to_return.append((time_slots.slot_id, str(time_slots.slot_time_start)))
    return to_return


def get_workshop_rooms():
    to_return = []
    for workshop_room in db_session.query(WorkshopRoom):
        to_return.append((workshop_room.room_id, workshop_room.room_name))
    return to_return


def get_time_slots_to_select(jam_id, user_id, admin_mode=False):
    workshop_slots = []
    for workshop_slot in db_session.query(WorkshopSlot).filter():
        workshop_slots.append({"title":str("{} - {}".format(workshop_slot.slot_time_start, workshop_slot.slot_time_end)), "slot_id":workshop_slot.slot_id, "workshops":[]})

    workshops = db_session.query(RaspberryJamWorkshop).filter(RaspberryJamWorkshop.jam_id == jam_id)
    if not admin_mode:
        workshops = workshops.filter(RaspberryJamWorkshop.workshop_id == Workshop.workshop_id, Workshop.workshop_hidden != 1)

    for workshop in workshops.all():
        if workshop.workshop.workshop_hidden == 0:
            pass

        if int(workshop.workshop_room.room_capacity) < int(workshop.workshop.workshop_limit):
            max_attendees = workshop.workshop_room.room_capacity
        else:
            max_attendees = workshop.workshop.workshop_limit
        names = ""
        attendee_ids = []
        for name in get_attendees_in_workshop(workshop.workshop_run_id):
            if str(name.order_id) == user_id or admin_mode:
                names = "{} {}, ".format(names, name.first_name.capitalize())
                attendee_ids.append(name.attendee_id)

        if workshop.users and len(workshop.users) > 0:
            volunteer = workshop.users[0].first_name
        else:
            volunteer = "None"

        new_workshop = {"workshop_room":workshop.workshop_room.room_name,
                        "workshop_title":workshop.workshop.workshop_title,
                        "workshop_description":workshop.workshop.workshop_description,
                        "workshop_limit":"{} / {}".format(len(get_attendees_in_workshop(workshop.workshop_run_id)), max_attendees),
                        "attendee_names":names,
                        "attendee_ids":attendee_ids,
                        "workshop_id":workshop.workshop_run_id,
                        "volunteer": volunteer,
                        "pilot": workshop.pilot}

        next((x for x in workshop_slots if x["slot_id"] == workshop.slot.slot_id), None)["workshops"].append(new_workshop)
        #workshop_slots[workshop.slot.slot_id]["workshops"].append(new_workshop)

    for workshop_slot_index, workshop_final_slot in enumerate(workshop_slots):
        workshop_slots[workshop_slot_index]["workshops"] = sorted(workshop_final_slot["workshops"], key=lambda x: x["workshop_room"], reverse=False)

    if not admin_mode:
        workshop_slots = workshop_slots[1:]
    return workshop_slots


def verify_attendee_id(id, jam_id):
    if id:
        attendees = db_session.query(Attendee).filter(Attendee.order_id == int(id), Attendee.jam_id == jam_id).all()
        if attendees:
            return attendees
    return False


def get_attendees_in_workshop(workshop_run_id, raw_result=False):
    attendees = db_session.query(RaspberryJamWorkshop, WorkshopAttendee, Workshop, Attendee).filter(RaspberryJamWorkshop.workshop_id == Workshop.workshop_id,
                                                                                                    RaspberryJamWorkshop.workshop_run_id == WorkshopAttendee.workshop_run_id,
                                                                                                    Attendee.attendee_id == WorkshopAttendee.attendee_id,
                                                                                                    RaspberryJamWorkshop.workshop_run_id == workshop_run_id).all()
    if raw_result:
        return attendees
    return_attendees = []
    for a in attendees:
        return_attendees.append(a.Attendee)
    return return_attendees


def get_if_workshop_has_space(jam_id, workshop_run_id):
    workshop = db_session.query(RaspberryJamWorkshop, RaspberryJam, WorkshopSlot, Workshop, WorkshopRoom).filter(
        RaspberryJamWorkshop.jam_id == jam_id,
        RaspberryJamWorkshop.workshop_room_id == WorkshopRoom.room_id,
        RaspberryJamWorkshop.slot_id == WorkshopSlot.slot_id,
        RaspberryJamWorkshop.jam_id == RaspberryJam.jam_id,
        RaspberryJamWorkshop.workshop_id == Workshop.workshop_id,
        RaspberryJamWorkshop.workshop_run_id == workshop_run_id).first()

    if int(workshop.WorkshopRoom.room_capacity) < int(workshop.Workshop.workshop_limit):
        max_attendees = workshop.WorkshopRoom.room_capacity
    else:
        max_attendees = workshop.Workshop.workshop_limit

    if len(get_attendees_in_workshop(workshop_run_id)) < int(max_attendees):
        return True
    return False

def get_if_attendee_booked_in_slot_for_workshop(attendee_id, workshop_run_id):
    slot_id = db_session.query(RaspberryJamWorkshop).filter(RaspberryJamWorkshop.workshop_run_id == workshop_run_id).first().slot_id

    workshops_attendee_in_slot = db_session.query(RaspberryJamWorkshop, WorkshopAttendee).filter(RaspberryJamWorkshop.workshop_run_id == WorkshopAttendee.workshop_run_id,
                                                                    WorkshopAttendee.attendee_id == attendee_id,
                                                                    RaspberryJamWorkshop.slot_id == slot_id).all()
    if workshops_attendee_in_slot:
        return True
    return False


def add_attendee_to_workshop(jam_id, attendee_id, workshop_run_id):
    attendee = db_session.query(Attendee).filter(Attendee.attendee_id == attendee_id).first()
    if get_if_workshop_has_space(jam_id, workshop_run_id) and not str(attendee.ticket_type).startswith("Parent") and not get_if_attendee_booked_in_slot_for_workshop(attendee_id, workshop_run_id):
        workshop_attendee = WorkshopAttendee(attendee_id=attendee_id, workshop_run_id=workshop_run_id)
        db_session.add(workshop_attendee)
        db_session.commit()
        return True
    else:
        return False


def remove_attendee_to_workshop(jam_id, attendee_id, workshop_run_id):
    booking = db_session.query(WorkshopAttendee).filter(WorkshopAttendee.attendee_id == attendee_id, WorkshopAttendee.workshop_run_id == workshop_run_id).first()
    if booking:
        db_session.delete(booking)
        db_session.commit()
        return True
    return False


def get_users():
    return db_session.query(LoginUser).all()


def get_user_details_from_username(username):
    return db_session.query(LoginUser).filter(LoginUser.username == username).first()


def get_user_from_cookie(cookie_value):
    cookie = db_session.query(LoginCookie).filter(LoginCookie.cookie_value == cookie_value).first()
    if cookie:
        return cookie.user
    return None


def create_user(username, password_hash, password_salt, first_name, surname, email):
    db_session.commit()
    user = LoginUser()
    user.username = username
    user.password_hash = password_hash
    user.password_salt = password_salt
    user.first_name = first_name
    user.surname = surname
    user.group_id = 1
    user.email = email

    db_session.add(user)
    db_session.commit()


def add_workshop_to_jam_from_catalog(jam_id, workshop_id, volunteer_id, slot_id, room_id, pilot):
    # TODO : Add a whole pile of checks here including if the volunteer is double booked, room is double booked etc.
    workshop = RaspberryJamWorkshop()
    workshop.jam_id = jam_id
    workshop.workshop_id = workshop_id
    workshop.slot_id = slot_id
    workshop.workshop_room_id = room_id
    workshop.pilot = pilot
    if int(volunteer_id) >= 0: # If the None user has been selected, then hit the else
        if workshop.users:
            workshop.users.append(db_session.query(LoginUser).filter(LoginUser.user_id == volunteer_id).first())
        else:
            workshop.users = [db_session.query(LoginUser).filter(LoginUser.user_id == volunteer_id).first(),]
    else:
        workshop.users = []
    db_session.add(workshop)
    db_session.flush()
    db_session.commit()


def remove_workshop_from_jam(workshop_run_id):
    print("Going to delete {}".format(workshop_run_id))
    workshop = db_session.query(RaspberryJamWorkshop).filter(RaspberryJamWorkshop.workshop_run_id == workshop_run_id).first()
    workshop.users = []
    db_session.commit()
    db_session.delete(workshop)

    for attendee in get_attendees_in_workshop(workshop_run_id, raw_result=True):
        db_session.delete(attendee.WorkshopAttendee)

    db_session.commit()


def get_cookie(cookie_value):
    return db_session.query(LoginCookie).filter(LoginCookie.cookie_value == cookie_value).first()


def new_cookie_for_user(user_id):
    new_cookie_value = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(10))
    new_cookie_expiry = datetime.datetime.now() + datetime.timedelta(hours=24)
    new_cookie = LoginCookie(cookie_value=new_cookie_value, user_id=user_id, cookie_expiry=new_cookie_expiry)
    db_session.add(new_cookie)
    db_session.commit()
    return new_cookie_value


def remove_cookie(cookie_value):
    cookie = db_session.query(LoginCookie).filter(LoginCookie.cookie_value == cookie_value).delete()
    db_session.commit()


def update_cookie_expiry(cookie_id):
    cookie = db_session.query(LoginCookie).filter(LoginCookie.cookie_id == cookie_id).first()
    if cookie and cookie.cookie_expiry > datetime.datetime.now():
        cookie.cookie_expiry = datetime.datetime.now() + datetime.timedelta(hours=24)
    db_session.commit()


def get_all_attendees_for_jam(jam_id):
    attendees = db_session.query(Attendee).filter(Attendee.jam_id == jam_id).order_by(Attendee.surname, Attendee.first_name).all()
    return attendees


def database_reset():
    db_session.query(WorkshopAttendee).delete()
    db_session.query(Attendee).delete()
    db_session.commit()


def get_volunteer_data(jam_id, current_user):
    time_slots = db_session.query(WorkshopSlot).all()

    workshop_data = db_session.query(RaspberryJamWorkshop).filter(RaspberryJamWorkshop.jam_id == jam_id).all()

    workshop_rooms_in_use = db_session.query(WorkshopRoom).filter(RaspberryJamWorkshop.workshop_room_id == WorkshopRoom.room_id,
                                                                  RaspberryJamWorkshop.jam_id == jam_id
                                                                  ).order_by(WorkshopRoom.room_name).all()

    for time_slot in time_slots:
        time_slot.rooms = []
        for workshop_room in workshop_rooms_in_use:
            room = deepcopy(workshop_room)
            room.workshop = RaspberryJamWorkshop()
            room.workshop.dummy = True
            time_slot.rooms.append(room)
        for workshop in workshop_data:
            for room in time_slot.rooms:
                if room.room_id == workshop.workshop_room_id and time_slot.slot_id == workshop.slot_id:
                    room.workshop = workshop
                    if room.workshop.workshop_room: # Room exists
                        if not workshop.workshop.workshop_volunteer_requirements:  # and does not have volunteers needed specified
                            workshop.workshop_needed_volunteers = room.workshop.workshop_room.room_volunteers_needed
                        elif int(workshop.workshop.workshop_volunteer_requirements) < 0:
                            workshop.workshop_needed_volunteers = 0
                        elif int(workshop.workshop.workshop_limit) != 0: # and does have volunteers specified while also does have attendees able to attend the workshop
                            max_attendees = min(int(workshop.workshop_room.room_capacity), int(workshop.workshop.workshop_limit))
                            volunteers_needed_from_attendees = 1 + (math.ceil(max_attendees / 10) * workshop.workshop.workshop_volunteer_requirements)
                            workshop.workshop_needed_volunteers = max(workshop.workshop_room.room_volunteers_needed, volunteers_needed_from_attendees) # Set volunteers needed to the calculated figure based on attendees, unless room minimum is greater.
                        else: # and does not have attendees for the workshop (for example, car parking etc)
                            workshop.workshop_needed_volunteers = workshop.workshop.workshop_volunteer_requirements

                    if not room.workshop.workshop_room:
                        room.workshop.bg_colour = grey
                    elif len(room.workshop.users) >= workshop.workshop_needed_volunteers:
                        room.workshop.bg_colour = green
                    else:
                        room.workshop.bg_colour = red

                    if room.workshop in current_user.workshop_runs:
                        room.workshop.signed_up = True
                        room.workshop.bg_colour = blue
                    else:
                        room.workshop.signed_up = False

    return time_slots, sorted(workshop_rooms_in_use, key=lambda x: x.room_name, reverse=False)


def get_workshop_timetable_data(jam_id): # Similar to get_volunteer_data(), but for the large TV with different colouring.
    time_slots = db_session.query(WorkshopSlot).all()[1:]

    workshop_data = db_session.query(RaspberryJamWorkshop).filter(RaspberryJamWorkshop.jam_id == jam_id, RaspberryJamWorkshop.workshop_id == Workshop.workshop_id , Workshop.workshop_hidden != 1).all()

    workshop_rooms_in_use = db_session.query(WorkshopRoom).filter(RaspberryJamWorkshop.workshop_room_id == WorkshopRoom.room_id,
                                                                  RaspberryJamWorkshop.jam_id == jam_id,
                                                                  RaspberryJamWorkshop.workshop_id == Workshop.workshop_id,
                                                                  Workshop.workshop_hidden != 1
                                                                  ).order_by(WorkshopRoom.room_name).all()

    for time_slot in time_slots:
        time_slot.rooms = []
        for workshop_room in workshop_rooms_in_use:
            room = deepcopy(workshop_room)
            room.workshop = RaspberryJamWorkshop()
            room.workshop.dummy = True
            time_slot.rooms.append(room)
        for workshop in workshop_data:
            for room in time_slot.rooms:
                if room.room_id == workshop.workshop_room_id and time_slot.slot_id == workshop.slot_id:
                    room.workshop = workshop
                    if int(workshop.workshop_room.room_capacity) < int(workshop.workshop.workshop_limit):
                        room.workshop.max_attendees = workshop.workshop_room.room_capacity
                    else:
                        room.workshop.max_attendees = workshop.workshop.workshop_limit


                    if not room.workshop.workshop_room:
                        room.workshop.bg_colour = grey
                    elif room.workshop.workshop.workshop_level == "Beginner":
                        room.workshop.bg_colour = green
                    elif room.workshop.workshop.workshop_level == "Intermediate":
                        room.workshop.bg_colour = orange
                    elif room.workshop.workshop.workshop_level == "Advanced":
                        room.workshop.bg_colour = red
                    elif room.workshop.workshop.workshop_level == "Not taught":
                        room.workshop.bg_colour = light_blue

    return time_slots, sorted(workshop_rooms_in_use, key=lambda x: x.room_name, reverse=False)


def set_user_workshop_runs_from_ids(user, jam_id, workshop_run_ids):
    sessions_block_ids = []
    workshops = db_session.query(RaspberryJamWorkshop).filter(RaspberryJamWorkshop.workshop_run_id.in_(workshop_run_ids), RaspberryJamWorkshop.jam_id == jam_id).all()
    for workshop in workshops: # Verify that the bookings being made don't collide with other bookings by same user for same slot.
        if workshop.slot_id in sessions_block_ids:
            print("Unable to book user in to slot, as they already have a colliding booking for that slot.")
            return False
        sessions_block_ids.append(workshop.slot_id)
    user.workshop_runs = workshops
    db_session.commit()
    return True


def remove_jam(jam_id):
    workshops = db_session.query(RaspberryJamWorkshop).filter(RaspberryJamWorkshop.jam_id == jam_id).all()
    for workshop in workshops:
        workshop.users = []
    db_session.commit()

    for workshop in workshops:
        db_session.delete(workshop)

    db_session.query(Attendee).filter(Attendee.jam_id == jam_id).delete()
    jam = db_session.query(RaspberryJam).filter(RaspberryJam.jam_id == jam_id).first()
    db_session.delete(jam)
    db_session.commit()


def select_jam(jam_id):
    config_option = db_session.query(Configuration).filter(Configuration.config_name == "jam_id").first()
    config_option.config_value = str(jam_id)
    db_session.commit()


def get_attending_volunteers(jam_id, only_attending_volunteers=False): # Get all the volunteers
    if only_attending_volunteers:
        attending_volunteers = db_session.query(VolunteerAttendance).filter(VolunteerAttendance.jam_id == jam_id,
                                                                            VolunteerAttendance.volunteer_attending)
        all_volunteers = []
        for user in attending_volunteers:
            all_volunteers.append(user.user)
    else:
        all_volunteers = db_session.query(LoginUser).all()
    for volunteer in all_volunteers:
        volunteer.current_jam_workshops_involved_in = []
        for workshop in volunteer.workshop_runs:
            if workshop.jam_id == jam_id: # Builds the workshops attached to each user
                volunteer.current_jam_workshops_involved_in.append("{}. {}".format(workshop.slot_id, workshop.workshop.workshop_title)) # Builds a list of strings to show in the tooltip
        volunteer.current_jam_workshops_involved_in = sorted(volunteer.current_jam_workshops_involved_in)

    all_volunteers = all_volunteers

    attending = db_session.query(VolunteerAttendance).filter(VolunteerAttendance.jam_id == jam_id).all()
    for attend in attending: # Matches volunteer attendance to users
        for volunteer in all_volunteers:
            if volunteer.user_id == attend.user.user_id:
                volunteer.attend = attend
    return sorted(sorted(all_volunteers, key=lambda x: x.surname, reverse=False), key=lambda x: hasattr(x, "attend"), reverse=True)


def add_volunteer_attendance(jam_id, user_id, attending_jam, attending_setup, attending_packdown, attending_food, notes):
    attendance = db_session.query(VolunteerAttendance).filter(VolunteerAttendance.jam_id == jam_id, VolunteerAttendance.user_id == user_id).first()
    new = False
    if not attendance:
        attendance = VolunteerAttendance()
        new = True
    attendance.user_id = user_id
    attendance.jam_id = jam_id
    attendance.volunteer_attending = attending_jam
    attendance.setup_attending = attending_setup
    attendance.packdown_attending = attending_packdown
    attendance.food_attending = attending_food
    attendance.notes = notes
    attendance.current_location = "Not arrived"
    if new:
        db_session.add(attendance)
    db_session.commit()


def get_users_not_responded_to_attendance(jam_id):
    all_volunteers = db_session.query(LoginUser).all()
    all_volunteers_responded_attendance = db_session.query(VolunteerAttendance).filter(VolunteerAttendance.jam_id == jam_id).all()
    all_volunteers_responded = []
    for volunteer in all_volunteers_responded_attendance:
        all_volunteers_responded.append(volunteer.user)
    #volunteers_not_responded = all_volunteers - all_volunteers_responded
    volunteers_not_responded = list(set(all_volunteers) - set(all_volunteers_responded))
    return volunteers_not_responded


def delete_workshop(workshop_id):
    workshop = db_session.query(Workshop).filter(Workshop.workshop_id == workshop_id).first()
    db_session.delete(workshop)
    db_session.commit()


def archive_workshop(workshop_id):
    workshop = db_session.query(Workshop).filter(Workshop.workshop_id == workshop_id).first()
    workshop.workshop_archived = 1
    db_session.commit()


def get_user_reset_code(user_id):
    new_code = str(uuid.uuid4()).replace("-", "")[:10]
    user = db_session.query(LoginUser).filter(LoginUser.user_id == user_id).first()
    user.reset_code = new_code
    db_session.commit()
    return new_code


def reset_password(username, reset_code, salt, hash):
    user = db_session.query(LoginUser).filter(LoginUser.username == username, LoginUser.reset_code == reset_code).first()
    if user:
        user.password_hash = hash
        user.password_salt = salt
        user.reset_code = None
        db_session.commit()
        return True
    return False


def set_group_for_user(user_id, group_id):
    user = db_session.query(LoginUser).filter(LoginUser.user_id == user_id).first()
    user.group_id = group_id
    db_session.commit()


def get_current_jam_id():
    jam_id = int(db_session.query(Configuration).filter(Configuration.config_name == "jam_id").first().config_value)
    return jam_id


def check_out_attendee(attendee_id):
    if len(attendee_id) < 6: # Check if volunteer
        volunteer_attendance = db_session.query(VolunteerAttendance).join(LoginUser).filter_by(user_id=attendee_id).filter(VolunteerAttendance.jam_id == get_current_jam_id()).first()
        volunteer_attendance.current_location = "Checked out"
    else:
        attendee = db_session.query(Attendee).filter(Attendee.attendee_id == attendee_id).first()
        attendee.current_location = "Checked out"
    db_session.commit()


def check_in_attendee(attendee_id):
    if len(attendee_id) < 6: # Check if volunteer
        volunteer_attendance = db_session.query(VolunteerAttendance).join(LoginUser).filter_by(user_id=attendee_id).filter(VolunteerAttendance.jam_id == get_current_jam_id()).first()
        volunteer_attendance.current_location = "Checked in"
    else:
        attendee = db_session.query(Attendee).filter(Attendee.attendee_id == attendee_id).first()
        attendee.current_location = "Checked in"
    db_session.commit()


def get_jam_details(jam_id):
    return db_session.query(RaspberryJam).filter(RaspberryJam.jam_id == jam_id).first()


def remove_workshop_file(file_id):
    file = db_session.query(WorkshopFile).filter(WorkshopFile.file_id == file_id).first()
    workshop_id = file.workshop_id
    db_session.delete(file)
    db_session.commit()
    os.remove(file.file_path)
    return workshop_id


def add_workshop_file(file_title, file_path, file_permission, workshop_id):
    if db_session.query(WorkshopFile).filter(WorkshopFile.workshop_id == workshop_id, WorkshopFile.file_path == file_path).first(): # If file of same name already exists
        return False
    file = WorkshopFile(file_title=file_title, file_path=file_path, file_permission=file_permission, workshop_id=workshop_id, file_edit_date=datetime.datetime.now())
    db_session.add(file)
    db_session.commit()
    return True


def get_file_for_download(workshop_id, file_path):
    file = db_session.query(WorkshopFile).filter(WorkshopFile.workshop_id == workshop_id, WorkshopFile.file_path == file_path).first()
    return file


def get_workshop_run(workshop_run_id):
    workshop_run = db_session.query(RaspberryJamWorkshop).filter(RaspberryJamWorkshop.workshop_run_id == workshop_run_id).first()
    return workshop_run