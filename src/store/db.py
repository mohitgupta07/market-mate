from abc import ABC, abstractmethod
import uuid
class DBStore(ABC):
  @abstractmethod
  def add_user(self):
    pass

  @abstractmethod
  def get_user(self, username:str):
    pass

  @abstractmethod
  def update_user(self, user_id:uuid.UUID):
    pass

  @abstractmethod
  def delete_user(self, user_id:uuid.UUID):
    pass

  @abstractmethod
  def get_conversation_history(self, userid:uuid.UUID):
    pass

  @abstractmethod
  def create_conversation(self, userid:uuid.UUID):
    pass

  @abstractmethod
  def add_message(self, userid:uuid.UUID, message:str):
    pass

