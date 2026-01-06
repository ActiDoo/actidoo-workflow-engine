# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from actidoo_wfe.helpers.modules import import_submodules


# We need to import all models here, to make them known to alembic
def load_all_models():
    import_submodules("actidoo_wfe.wf.models")
    import_submodules("actidoo_wfe.async_scheduling")
    import_submodules("actidoo_wfe.session")
    import_submodules("actidoo_wfe.cache")
