import re

from lxml import etree
from lxml.builder import E

from datetime import datetime, date

from django.db.models import get_model
from django.core.exceptions import ImproperlyConfigured

from oscar.core.loading import _pluck_classes

AmazonProfile = get_model('oscar_mws', 'AmazonProfile')
ProductAttributeValue = get_model('catalogue', 'ProductAttributeValue')


def load_mapper(name, default=None):
    name = name or default
    try:
        module_label, class_name = name.rsplit('.', 1)
    except ValueError:
        raise ImproperlyConfigured(
            "cannot find product mapper class {0}".format(name)
        )
    imported_module = __import__(module_label, fromlist=[class_name])
    try:
        return _pluck_classes([imported_module], [class_name])[0]
    except IndexError:
        return None


class BaseProductDataMapper(object):
    product_type = None

    def get_product_data(self, product, **kwargs):
        pt_elem = getattr(E, self.product_type)()

        attr_values = ProductAttributeValue.objects.filter(
            product=product,
            attribute__code__in=self.ATTRIBUTE_MAPPING.keys()
        ).select_related('attribute')

        values = sorted(
            [(self.ATTRIBUTE_MAPPING.get(p.attribute.code), p.value) for p in attr_values]
        )
        for name, value in values:
            pt_elem.append(getattr(E, name)(value))

        return getattr(E, self.base_type)(E.ProductType(pt_elem))


class BaseProductMapper(object):

    def convert_camel_case(self, name):
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _get_value_from(self, obj, attr):
        """
        Get value from the *obj* for the given attribute name in *attr*. First
        this method attempts to retrieve the value from a ``get_<attr>``
        method then falls back to a simple attribute.
        """
        method_name = 'get_{0}'.format(attr)
        if hasattr(obj, method_name):
            return getattr(obj, method_name)()
        value = getattr(obj, attr, None)
        #TODO this should be limited to only fields that are required in
        # the feed.
        #if not value:
        #    raise AttributeError(
        #        "can't find attribute or function for {0}. Make sure you "
        #        "have either of them defined and try again".format(attr)
        #    )
        return value

    def get_value_element(self, product, attr_name):
        pyattr = self.convert_camel_case(attr_name)

        attr_value = self._get_value_from(product.amazon_profile, pyattr)
        if not attr_value:
            attr_value = self._get_value_from(product, pyattr)
        if not attr_value:
            attr_value = self._get_value_from(self, pyattr)

        # if we still have no value we assume it is optional and
        # we just leave it out of the generated XML.
        if not attr_value:
            return None

        if isinstance(attr_value, etree._Element):
            return attr_value

        if not isinstance(attr_value, basestring):
            attr_value = self.serialise(attr_value)
        elem = etree.Element(attr_name)
        elem.text = attr_value
        return elem


class ProductMapper(BaseProductMapper):
    BASE_ATTRIBUTES = [
        "SKU",
        "StandardProductID",
        "ProductTaxCode",
        "LaunchDate",
        "DiscontinueDate",
        "ReleaseDate",
        "ExternalProductUrl",
        "OffAmazonChannel",
        "OnAmazonChannel",
        "Condition",
        "Rebate",
        "ItemPackageQuantity",
        "NumberOfItems",
    ]
    DESCRIPTION_DATA_ATTRIBUTES = [
        "Title",
        "Brand",
        "Designer",
        "Description",
        "BulletPoint",
        "ItemDimensions",
        "PackageDimensions",
        "PackageWeight",
        "ShippingWeight",
        "MerchantCatalogNumber",
        "MSRP",
        "MaxOrderQuantity",
        "SerialNumberRequired",
        "Prop65",
        "LegalDisclaimer",
        "Manufacturer",
        "MfrPartNumber",
        "SearchTerms",
        "PlatinumKeywords",
        "RecommendedBrowseNode",
        "Memorabilia",
        "Autographed",
        "UsedFor",
        "ItemType",
        "OtherItemAttributes",
        "TargetAudience",
        "SubjectContent",
        "IsGiftWrapAvailable",
        "IsGiftMessageAvailable",
        "IsDiscontinuedByManufacturer",
        "MaxAggregateShipQuantity",
    ]

    def _add_attributes(self, product, elem, attr_names):
        try:
            product.amazon_profile
        except AmazonProfile.DoesNotExist:
            # Assign to the product to make sure it is accessible without
            # having to look it up on the product again
            product.amazon_profile = AmazonProfile.objects.create(
                product=product
            )

        for attr in attr_names:
            attr_elem = self.get_value_element(product, attr)

            if attr_elem is not None:
                elem.append(attr_elem)

    def serialise(self, value):
        """
        Very basic an naive serialiser function for python types to the
        Amazon XML representation.
        """
        if not value:
            return u''
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return unicode(value)

    def get_product_xml(self, product):
        product_elem = E.Product()
        self._add_attributes(product, product_elem, self.BASE_ATTRIBUTES)

        desc_elem = etree.SubElement(product_elem, 'DescriptionData')
        self._add_attributes(
            product,
            desc_elem,
            self.DESCRIPTION_DATA_ATTRIBUTES
        )

        mapper = self.PRODUCT_DATA_MAPPERS.get(product.product_class.slug)
        if mapper:
            sub_tree = mapper().get_product_data(product)
            if sub_tree is not None:
                pd_elem = E.ProductData()
                pd_elem.append(sub_tree)
                product_elem.append(pd_elem)
        return product_elem


class InventoryProductMapper(BaseProductMapper):
    pass
