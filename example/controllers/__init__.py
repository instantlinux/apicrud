"""__init__.py

Initialize each controller and return list of resources for service registry

created 14-jan-2020 by richb@instantlinux.net
"""

from . import account, auth, category, contact, credential, grant, list, \
    location, message, person, settings, tz


def resources():
    """ Runs the __init__ function for each controller, which
    makes the resource name and object available as singletons for
    use with flask

    returns:
      list of resources initialized
    """

    results = []
    for controller in [
            account.AccountController,
            auth.AuthController,
            category.CategoryController,
            contact.ContactController,
            credential.CredentialController,
            grant.GrantController,
            list.ListController,
            location.LocationController,
            message.MessageController,
            person.PersonController,
            # profile.ProfileController,
            settings.SettingsController,
            tz.TZController]:
        results.append(controller().resource)
    return results
