"""_init.py

Initialize each controller

created 14-jan-2020 by richb@instantlinux.net
"""

from . import account, auth, category, contact, grant, list, location, \
    message, person, settings, tz


def controllers():
    for controller in [
            account.AccountController,
            auth.AuthController,
            category.CategoryController,
            contact.ContactController,
            grant.GrantController,
            list.ListController,
            location.LocationController,
            message.MessageController,
            person.PersonController,
            # profile.ProfileController,
            settings.SettingsController,
            tz.TZController]:
        controller()
