"""Factory Boy factories for generating test domain objects."""

import uuid
from datetime import datetime, timezone, date, timedelta

import factory
from factory import LazyFunction, Sequence, SubFactory
from faker import Faker

fake = Faker()


class OwnerFactory(factory.Factory):
    class Meta:
        model = dict

    owner_id = LazyFunction(lambda: str(uuid.uuid4()))
    first_name = factory.LazyFunction(fake.first_name)
    last_name = factory.LazyFunction(fake.last_name)
    phone_number = factory.LazyFunction(lambda: fake.numerify("###-###-####"))
    sms_number = None
    email = factory.LazyAttribute(lambda o: f"{o.first_name.lower()}.{o.last_name.lower()}@example.com")
    alternate_name = None
    emergency_contact_name = None
    emergency_contact_phone = None
    vet_name = None
    vet_phone = None
    notes = None


class DogFactory(factory.Factory):
    class Meta:
        model = dict

    dog_id = LazyFunction(lambda: str(uuid.uuid4()))
    owner_id = LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.LazyFunction(fake.first_name)
    breed = factory.Iterator(["Golden Retriever", "Labrador", "Poodle", "Beagle", "Chihuahua"])
    size_class = factory.Iterator(["XS", "S", "M", "L", "XL"])
    medical_status = "Healthy"
    medical_notes = None
    description = None
    weight_lbs = None
    date_of_birth = None
    photo_url = None
    notes = None
    vaccination_records = None


class KennelFactory(factory.Factory):
    class Meta:
        model = dict

    kennel_id = LazyFunction(lambda: str(uuid.uuid4()))
    kennel_number = Sequence(lambda n: f"K-{n+1:02d}")
    kennel_type = "Large"
    max_size_class = "XL"
    sqft = 30.0
    features = "interior and exterior space"
    description = None
    active = True
    provisioned_from_config = True


class ReservationFactory(factory.Factory):
    class Meta:
        model = dict

    reservation_id = LazyFunction(lambda: str(uuid.uuid4()))
    dog_id = LazyFunction(lambda: str(uuid.uuid4()))
    kennel_id = LazyFunction(lambda: str(uuid.uuid4()))
    dropoff_datetime = LazyFunction(lambda: datetime.now(timezone.utc).replace(hour=9, minute=0, second=0))
    pickup_datetime = LazyFunction(lambda: (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=10, minute=0, second=0))
    pickup_open_ended = False
    notes = None


class ActivityFactory(factory.Factory):
    class Meta:
        model = dict

    activity_id = LazyFunction(lambda: str(uuid.uuid4()))
    reservation_id = LazyFunction(lambda: str(uuid.uuid4()))
    activity_type = "Nature Walk"
    scheduled_date = LazyFunction(lambda: date.today())
    performed_datetime = None
    performed_by = None
    qualifies_for_pacfa_exception = True
    notes = None


class IncidentFactory(factory.Factory):
    class Meta:
        model = dict

    incident_id = LazyFunction(lambda: str(uuid.uuid4()))
    dog_id = LazyFunction(lambda: str(uuid.uuid4()))
    reservation_id = LazyFunction(lambda: str(uuid.uuid4()))
    incident_type = "Behavioral"
    description = "Dog showed aggression toward staff during feeding."
    occurred_datetime = LazyFunction(lambda: datetime.now(timezone.utc))
    visible_to_owner = False
    owner_notified = False
