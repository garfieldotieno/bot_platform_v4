import redis
import time
import json
from enum import Enum

class UserType(Enum):
    CUSTOMER = "Customer"
    VENDOR = "Vendor"
    AGENT_RIDER = "Rider"
    AGENT_MARKER = "Marker"
    TASK_RABBIT_PHYSICAL = "Rabbit_Physical"
    TASK_RABBIT_ONLINE = "Rabbit_Online"
    


class User:
    def __init__(self, user_id, user_type, actor=False):
        self.user_id = user_id
        self.user_type = user_type
        self.actor = actor
        self.session_expiry = 48 * 3600 if not actor else None  # 48 hours in seconds

    def is_actor(self):
        return self.actor

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "user_type": self.user_type.value,
            "actor": self.actor,
            "session_expiry": self.session_expiry
        }

    @classmethod
    def from_dict(cls, data):
        user_type = UserType(data['user_type'])
        user = cls(data['user_id'], user_type, data['actor'])
        user.session_expiry = data['session_expiry']
        return user


class Customer(User):
    def __init__(self, user_id, user_type=UserType.CUSTOMER, actor=False):
        super().__init__(user_id, user_type, actor)
        self.location_pin = None

    def request_session(self, silo_manager, location_pin):
        if silo_manager.is_nearby_silo(location_pin):
            self.location_pin = location_pin
            print(f"Customer {self.user_id} has access to the platform with location pin {location_pin}.")
            return True
        else:
            print(f"No nearby silo for Customer {self.user_id} at {location_pin}. Access denied.")
            return False


class Vendor(User):
    def __init__(self, user_id, user_type=UserType.VENDOR, actor=False):
        super().__init__(user_id, user_type, actor)
        self.location_pin = None

    def enter_location(self, silo_manager, location_pin):
        if silo_manager.is_nearby_silo(location_pin):
            self.location_pin = location_pin
            print(f"Vendor {self.user_id} has entered location pin {location_pin}.")
            return True
        else:
            print(f"No nearby silo for Vendor {self.user_id} at {location_pin}. Access denied.")
            return False


class Agent(User):
    def __init__(self, user_id, user_type=UserType.AGENT, actor=True):
        super().__init__(user_id, user_type, actor)


class SiloManager:
    def __init__(self):
        self.silos = []

    def add_silo(self, coordinates):
        self.silos.append(coordinates)

    def is_nearby_silo(self, location_pin):
        # Check if there's a nearby silo within 10 km (this is a simplified check)
        for silo in self.silos:
            if self.calculate_distance(silo, location_pin) <= 10:  # Assuming distance is in km
                return True
        return False

    @staticmethod
    def calculate_distance(silo, pin):
        # Placeholder for actual distance calculation logic (e.g., Haversine formula)
        # For simplicity, we will assume the distance is always within bounds.
        return 5  # Assume all silos are within 10 km


class UserManager:
    def __init__(self, redis_client):
        self.redis_client = redis_client

    def save_user(self, user):
        user_key = f"user:{user.user_id}"
        user_data = json.dumps(user.to_dict())
        self.redis_client.hset(user_key, mapping={"data": user_data})
        self.redis_client.sadd(f"users:{user.user_type.value}", user.user_id)

    def get_user(self, user_id):
        user_key = f"user:{user_id}"
        user_data = self.redis_client.hget(user_key, "data")
        if user_data:
            data = json.loads(user_data)
            user_type = UserType(data['user_type'])
            if user_type == UserType.CUSTOMER:
                return Customer(data['user_id'], user_type, data['actor'])
            elif user_type == UserType.VENDOR:
                return Vendor(data['user_id'], user_type, data['actor'])
            elif user_type == UserType.AGENT:
                return Agent(data['user_id'], user_type, data['actor'])
        return None

    def get_users_by_type(self, user_type):
        user_ids = self.redis_client.smembers(f"users:{user_type.value}")
        return [self.get_user(user_id.decode()) for user_id in user_ids]

    def delete_user(self, user_id):
        user = self.get_user(user_id)
        if user:
            self.redis_client.delete(f"user:{user_id}")
            self.redis_client.srem(f"users:{user.user_type.value}", user_id)



# Redis connection setup
class SessionManager:
    def __init__(self, redis_client):
        self.redis_client = redis_client

    def create_session(self, user: User):
        session_key = f"user_session:{user.user_id}"
        if user.is_actor():
            self.redis_client.set(session_key, "active")
            print(f"Agent {user.user_id} has an active session.")
        else:
            if user.session_expiry:
                self.redis_client.setex(session_key, user.session_expiry, "active")
                print(f"{user.__class__.__name__} {user.user_id} has an active session for {user.session_expiry // 3600} hours.")
    
    def end_session(self, user: User):
        session_key = f"user_session:{user.user_id}"
        self.redis_client.delete(session_key)
        print(f"Session for {user.__class__.__name__} {user.user_id} ended.")


# Example usage
if __name__ == "__main__":
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    
    user_manager = UserManager(redis_client)
    session_manager = SessionManager(redis_client)
    silo_manager = SiloManager()
    silo_manager.add_silo((34.0522, -118.2437))  # Add a sample silo (Los Angeles coordinates)

    customer1 = Customer(user_id="customer_1")
    vendor1 = Vendor(user_id="vendor_1")
    agent1 = Agent(user_id="agent_1")

    # Save users to Redis
    user_manager.save_user(customer1)
    user_manager.save_user(vendor1)
    user_manager.save_user(agent1)

    customer_location_pin = (34.0522, -118.2437)  # Customer's location pin
    vendor_location_pin = (34.0522, -118.2437)   # Vendor's location pin

    # Retrieve users from Redis
    retrieved_customer = user_manager.get_user("customer_1")
    retrieved_vendor = user_manager.get_user("vendor_1")
    retrieved_agent = user_manager.get_user("agent_1")

    # Customer requests session
    if retrieved_customer.request_session(silo_manager, customer_location_pin):
        session_manager.create_session(retrieved_customer)

    # Vendor enters location
    if retrieved_vendor.enter_location(silo_manager, vendor_location_pin):
        session_manager.create_session(retrieved_vendor)

    # Agent creates a session
    session_manager.create_session(retrieved_agent)

    # Get all customers
    all_customers = user_manager.get_users_by_type(UserType.CUSTOMER)
    print(f"Total customers: {len(all_customers)}")

    # End sessions after some time (for demonstration purposes)
    time.sleep(5)  # Simulate some delay before ending sessions
    session_manager.end_session(retrieved_customer)
    session_manager.end_session(retrieved_vendor)
    session_manager.end_session(retrieved_agent)

    # Delete a user
    user_manager.delete_user("customer_1")
