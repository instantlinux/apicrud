"""__init__.py

Initialize each controller and return list of resources for service registry

created 14-jan-2020 by richb@instantlinux.net
"""
from apicrud.controllers import account, apikey, auth, category, contact, \
    credential, grant, location, metric, person, profile, scope, settings, \
    trashcan, tz

from . import list, message


def resources():
    """Runs the __init__ function for each controller, which
    makes the resource name and object available as singletons for
    use with flask. The apicrud.BasicCRUD class defines default
    functions for the most common endpoints. The simplest custom
    controller you can create here in this directory is:
    ```
    from apicrud import BasicCRUD

    class MyController(BasicCRUD):
        def __init__(self):
            super().__init__(resource='myresource')
    ```

    See the apicrud.controllers class definitions for examples of
    ways to override or add endpoints.

    Returns: (list<str>) of resources initialized
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
            trashcan.TrashcanController,
            tz.TZController]:
        results.append(controller().resource)
    return results
