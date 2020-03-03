from collections import OrderedDict

from sqlalchemy.exc import DataError, InternalError, ProgrammingError

from qwc_services_core.database import DatabaseEngine
from qwc_services_core.permissions_reader import PermissionsReader
from qwc_services_core.runtime_config import RuntimeConfig
from dataset_features_provider import DatasetFeaturesProvider


class DataService():
    """DataService class

    Manage reading and writing of dataset features.
    """

    def __init__(self, tenant, logger):
        """Constructor

        :param str tenant: Tenant ID
        :param Logger logger: Application logger
        """
        self.tenant = tenant
        self.logger = logger
        self.resources = self.load_resources()
        self.permissions_handler = PermissionsReader(tenant, logger)
        self.db_engine = DatabaseEngine()

    def index(self, identity, dataset, bbox, crs, filterexpr):
        """Find dataset features inside bounding box.

        :param str identity: User identity
        :param str dataset: Dataset ID
        :param str bbox: Bounding box as '<minx>,<miny>,<maxx>,<maxy>' or None
        :param str crs: Client CRS as 'EPSG:<srid>' or None
        :param str filterexpr: JSON serialized array of filter expressions:
        [["<attr>", "<op>", "<value>"], "and|or", ["<attr>", "<op>", "<value>"]]
        """
        dataset_features_provider = self.dataset_features_provider(
            identity, dataset
        )
        if dataset_features_provider is not None:
            # check read permission
            if not dataset_features_provider.readable():
                return {
                    'error': "Dataset not readable",
                    'error_code': 405
                }

            if bbox is not None:
                # parse and validate input bbox
                bbox = dataset_features_provider.parse_bbox(bbox)
                if bbox is None:
                    return {
                        'error': "Invalid bounding box",
                        'error_code': 400
                    }
            srid = None
            if crs is not None:
                # parse and validate unput CRS
                srid = dataset_features_provider.parse_crs(crs)
                if srid is None:
                    return {
                        'error': "Invalid CRS",
                        'error_code': 400
                    }
            if filterexpr is not None:
                # parse and validate input filter
                filterexpr = dataset_features_provider.parse_filter(filterexpr)
                if filterexpr[0] is None:
                    return {
                        'error': (
                            "Invalid filter expression: %s" % filterexpr[1]
                        ),
                        'error_code': 400
                    }

            try:
                feature_collection = dataset_features_provider.index(
                    bbox, srid, filterexpr
                )
            except (DataError, ProgrammingError) as e:
                self.logger.error(e)
                return {
                    'error': (
                        "Feature query failed. Please check filter expression "
                        "values and operators."
                    ),
                    'error_code': 400
                }
            return {'feature_collection': feature_collection}
        else:
            return {'error': "Dataset not found or permission error"}

    def show(self, identity, dataset, id, crs):
        """Get a dataset feature.

        :param str identity: User identity
        :param str dataset: Dataset ID
        :param int id: Dataset feature ID
        :param str crs: Client CRS as 'EPSG:<srid>' or None
        """
        dataset_features_provider = self.dataset_features_provider(
            identity, dataset
        )
        srid = None
        if crs is not None:
            # parse and validate unput CRS
            srid = dataset_features_provider.parse_crs(crs)
            if srid is None:
                return {
                    'error': "Invalid CRS",
                    'error_code': 400
                }
        if dataset_features_provider is not None:
            # check read permission
            if not dataset_features_provider.readable():
                return {
                    'error': "Dataset not readable",
                    'error_code': 405
                }

            feature = dataset_features_provider.show(id, srid)
            if feature is not None:
                return {'feature': feature}
            else:
                return {'error': "Feature not found"}
        else:
            return {'error': "Dataset not found or permission error"}

    def create(self, identity, dataset, feature):
        """Create a new dataset feature.

        :param str identity: User identity
        :param str dataset: Dataset ID
        :param object feature: GeoJSON Feature
        """
        dataset_features_provider = self.dataset_features_provider(
            identity, dataset
        )
        if dataset_features_provider is not None:
            # check create permission
            if not dataset_features_provider.creatable():
                return {
                    'error': "Dataset not creatable",
                    'error_code': 405
                }

            # validate input feature
            validation_errors = dataset_features_provider.validate(feature)
            if not validation_errors:
                # create new feature
                try:
                    feature = dataset_features_provider.create(feature)
                except (DataError, InternalError, ProgrammingError) as e:
                    self.logger.error(e)
                    return {
                        'error': "Feature commit failed",
                        'error_details': {
                            'data_errors': ["Feature could not be created"],
                        },
                        'error_code': 422
                    }
                return {'feature': feature}
            else:
                return {
                    'error': "Feature validation failed",
                    'error_details': validation_errors,
                    'error_code': 422
                }
        else:
            return {'error': "Dataset not found or permission error"}

    def update(self, identity, dataset, id, feature):
        """Update a dataset feature.

        :param str identity: User identity
        :param str dataset: Dataset ID
        :param int id: Dataset feature ID
        :param object feature: GeoJSON Feature
        """
        dataset_features_provider = self.dataset_features_provider(
            identity, dataset
        )
        if dataset_features_provider is not None:
            # check update permission
            if not dataset_features_provider.updatable():
                return {
                    'error': "Dataset not updatable",
                    'error_code': 405
                }

            # validate input feature
            validation_errors = dataset_features_provider.validate(feature)
            if not validation_errors:
                # update feature
                try:
                    feature = dataset_features_provider.update(id, feature)
                except (DataError, InternalError, ProgrammingError) as e:
                    self.logger.error(e)
                    return {
                        'error': "Feature commit failed",
                        'error_details': {
                            'data_errors': ["Feature could not be updated"],
                        },
                        'error_code': 422
                    }
                if feature is not None:
                    return {'feature': feature}
                else:
                    return {'error': "Feature not found"}
            else:
                return {
                    'error': "Feature validation failed",
                    'error_details': validation_errors,
                    'error_code': 422
                }
        else:
            return {'error': "Dataset not found or permission error"}

    def destroy(self, identity, dataset, id):
        """Delete a dataset feature.

        :param str identity: User identity
        :param str dataset: Dataset ID
        :param int id: Dataset feature ID
        """
        dataset_features_provider = self.dataset_features_provider(
            identity, dataset
        )
        if dataset_features_provider is not None:
            # check delete permission
            if not dataset_features_provider.deletable():
                return {
                    'error': "Dataset not deletable",
                    'error_code': 405
                }

            if dataset_features_provider.destroy(id):
                return {}
            else:
                return {'error': "Feature not found"}
        else:
            return {'error': "Dataset not found or permission error"}

    def dataset_features_provider(self, identity, dataset):
        """Return DatasetFeaturesProvider if available and permitted.

        :param str identity: User identity
        :param str dataset: Dataset ID
        """
        dataset_features_provider = None

        # check permissions
        permissions = self.dataset_edit_permissions(
            dataset, identity
        )
        if permissions:
            # create DatasetFeaturesProvider
            dataset_features_provider = DatasetFeaturesProvider(
                permissions, self.db_engine
            )

        return dataset_features_provider

    def load_resources(self):
        """Load service resources from config."""
        # read config
        config_handler = RuntimeConfig("data", self.logger)
        config = config_handler.tenant_config(self.tenant)

        # get service resources
        datasets = {}
        for resource in config.resources().get('datasets', []):
            datasets[resource['name']] = resource

        return {
            'datasets': datasets
        }

    def dataset_edit_permissions(self, dataset, identity):
        """Return dataset edit permissions if available and permitted.

        :param str dataset: Dataset ID
        :param obj identity: User identity
        """
        # find resource for requested dataset
        resource = self.resources['datasets'].get(dataset)
        if resource is None:
            # dataset not found
            return {}

        # get permissions for dataset
        resource_permissions = self.permissions_handler.resource_permissions(
            'data_datasets', identity, dataset
        )
        if not resource_permissions:
            # dataset not permitted
            return {}

        # combine permissions
        permitted_attributes = set()
        writable = False
        creatable = False
        readable = False
        updatable = False
        deletable = False

        for permission in resource_permissions:
            # collect permitted attributes
            permitted_attributes.update(permission.get('attributes', []))

            # allow writable and CRUD actions if any role permits them
            writable |= permission.get('writable', False)
            creatable |= permission.get('creatable', False)
            readable |= permission.get('readable', False)
            updatable |= permission.get('updatable', False)
            deletable |= permission.get('deletable', False)

        # make writable consistent with CRUD actions
        writable |= creatable and readable and updatable and deletable

        # make CRUD actions consistent with writable
        creatable |= writable
        readable |= writable
        updatable |= writable
        deletable |= writable

        permitted = creatable or readable or updatable or deletable
        if not permitted:
            # no CRUD action permitted
            return {}

        # filter by permissions
        attributes = [
            field['name'] for field in resource['fields']
            if field['name'] in permitted_attributes
        ]

        fields = {}
        for field in resource['fields']:
            if field['name'] in permitted_attributes:
                fields[field['name']] = field

        # NOTE: 'geometry' is None for datasets without geometry
        geometry = resource.get('geometry', {})

        return {
            "dataset": resource['name'],
            "database": resource['database'],
            "schema": resource['schema'],
            "table_name": resource['table_name'],
            "primary_key": resource['primary_key'],
            "attributes": attributes,
            "fields": fields,
            "geometry_column": geometry.get('geometry_column'),
            "geometry_type": geometry.get('geometry_type'),
            "srid": geometry.get('srid'),
            "writable": writable,
            "creatable": creatable,
            "readable": readable,
            "updatable": updatable,
            "deletable": deletable
        }
