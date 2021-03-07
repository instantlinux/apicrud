"""__init__.py

Initialize each controller and return list of resources for service registry

created 14-jan-2020 by richb@instantlinux.net
"""

from . import account, apikey, auth, category, contact, credential, grant, \
    list, location, message, metric, person, profile, scope, settings, tz


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
            apikey.APIkeyController,
            auth.AuthController,
            category.CategoryController,
            contact.ContactController,
            credential.CredentialController,
            grant.GrantController,
            list.ListController,
            location.LocationController,
            message.MessageController,
            metric.MetricController,
            person.PersonController,
            profile.ProfileController,
            scope.ScopeController,
            settings.SettingsController,
            tz.TZController]:
        results.append(controller().resource)
    return results
