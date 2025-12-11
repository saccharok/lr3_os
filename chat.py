import json
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime

@dataclass
class Message:
    sender: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class Chat:
    chatId: str
    chatType: str
    participants: List[str] = field(default_factory=list)
    chatName: Optional[str] = None
    admin: Optional[str] = None
    historyDir: str = "chats_story"
    
    #загрузить историю чата
    def loadHistory(self) -> List[Message]:
        historyPath = os.path.join(self.historyDir, f"{self.chatId}.json")
        if not os.path.exists(historyPath):
            return []
        
        try:
            with open(historyPath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = []
                for msg in data.get('messages', []):
                    messages.append(Message(
                        sender=msg['sender'],
                        content=msg['content'],
                        timestamp=msg['timestamp']
                    ))
                return messages
        except Exception as e:
            print(f"ошибка загрузки истории {self.chatId}: {e}")
            return []
    
    #сохранить историю чата (сразу после ввода сообщения)
    def saveHistory(self, messages: List[Message]):
        historyPath = os.path.join(self.historyDir, f"{self.chatId}.json")
        try:
            os.makedirs(self.historyDir, exist_ok=True)
            with open(historyPath, 'w', encoding='utf-8') as f:
                json.dump({
                    'messages': [
                        {
                            'sender': msg.sender,
                            'content': msg.content,
                            'timestamp': msg.timestamp
                        }
                        for msg in messages
                    ]
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"ошибка сохранения истории {self.chatId}: {e}")
    
    #добавить сообщение
    def addMessage(self, sender: str, content: str) -> Message:
        message = Message(sender=sender, content=content)
        history = self.loadHistory()
        history.append(message)
        self.saveHistory(history)  #и в JSON
        return message
    
    #получить последние сообщения
    def getLastMessages(self, count: int = 10) -> List[Message]:
        history = self.loadHistory()
        return history[-count:] if history else []
    
    #показать историю чата
    def showHistory(self, limit: Optional[int] = None):
        history = self.loadHistory()
        if not history:
            print(f"[{self.chatId}] история пуста")
            return
        
        if limit:
            history = history[-limit:]
        
        print(f"\n--- История чата: {self.chatName or self.chatId} ---")
        for msg in history:
            print(f"{msg.sender}: {msg.content}")
        print("---" * 15)
    
    #проверить доступ
    def canAccess(self, username: str) -> bool:
        return username in self.participants
    
    #получить информацию о чате
    def getInfo(self) -> Dict:
        return {
            'chatId': self.chatId,
            'type': self.chatType,
            'participants': self.participants,
            'chatName': self.chatName,
            'admin': self.admin
        }
    
    #обновить информацию о чате
    def updateInfo(self, **kwargs):
        if 'participants' in kwargs:
            self.participants = kwargs['participants']
        if 'chatName' in kwargs:
            self.chatName = kwargs['chatName']
        if 'admin' in kwargs:
            self.admin = kwargs['admin']

#для загрузки всех чатов
def loadAllChats(chatsPath: str = "chats.json") -> Dict[str, Chat]:
    try:
        with open(chatsPath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            chats = {}
            for chatId, info in data.get('chats', {}).items():
                chats[chatId] = Chat(
                    chatId=chatId,
                    chatType=info['type'],
                    participants=info['participants'],
                    chatName=info.get('chatName'),
                    admin=info.get('admin')
                )
            return chats
    except Exception as e:
        print(f"ошибка загрузки чатов: {e}")
        return {}

#для создания нового чата
def createChat(chatId: str, chatType: str, participants: List[str], 
               chatName: Optional[str] = None, admin: Optional[str] = None) -> Chat:
    return Chat(
        chatId=chatId,
        chatType=chatType,
        participants=participants,
        chatName=chatName,
        admin=admin
    )

#для сохранения чатов
def saveChats(chats: Dict[str, Chat], chatsPath: str = "chats.json"):
    try:
        data = {'chats': {}}
        for chatId, chat in chats.items():
            data['chats'][chatId] = chat.getInfo()
        
        with open(chatsPath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"ошибка сохранения чатов: {e}")

#для поиска чатов пользователя
def findUserChats(username: str, chats: Dict[str, Chat]) -> List[str]:
    return [chatId for chatId, chat in chats.items() if username in chat.participants]