import socket as locsoc
import json
import threading
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import chat

@dataclass
class ClientSession:
    username: str
    socket: locsoc.socket
    address: Tuple[str, int]
    status: str = "online"

@dataclass
class Server:
    host: str = 'localhost'
    port: int = 8888
    serverSocket: Optional[locsoc.socket] = None
    running: bool = False
    clientsPath: str = "clients.json"
    usersDir: str = "clients_story"
    chats: Dict[str, chat.Chat] = field(default_factory=dict)
    onlineUsers: Dict[str, ClientSession] = field(default_factory=dict)
    
    #загрузка клиентов
    def loadClients(self) -> Dict:
        try:
            with open(self.clientsPath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"ошибка загрузки клиентов: {e}")
            return {"clients": {}}
    
    #сохранить клиентов
    def saveClients(self, clientsData: Dict):
        try:
            with open(self.clientsPath, 'w', encoding='utf-8') as f:
                json.dump(clientsData, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"ошибка сохранения клиентов: {e}")
    
    #загрузить пользователя
    def loadUser(self, username: str) -> Optional[Dict]:
        userPath = os.path.join(self.usersDir, f"{username}.json")
        try:
            with open(userPath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"ошибка загрузки пользователя {username}: {e}")
            return None
    
    #сохранить пользователя с обновлением статуса
    def saveUser(self, username: str, userData: Dict, updateStatus: bool = True):
        userPath = os.path.join(self.usersDir, f"{username}.json")
        try:
            os.makedirs(self.usersDir, exist_ok=True)
            
            if updateStatus and username in self.onlineUsers:
                userData['status'] = 'online'
            elif updateStatus:
                userData['status'] = 'offline'
            
            with open(userPath, 'w', encoding='utf-8') as f:
                json.dump(userData, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"ошибка сохранения пользователя {username}: {e}")
    
    #загрузить чаты
    def loadChats(self):
        self.chats = chat.loadAllChats()
    
    #сохранить чаты
    def saveChats(self):
        chat.saveChats(self.chats)
    
    #аутентификация
    def authenticate(self, username: str, password: str) -> bool:
        clientsData = self.loadClients()
        if username in clientsData.get('clients', {}):
            storedPass = clientsData['clients'][username]['password']
            return storedPass == password
        return False
    
    #регистрация
    def handleRegister(self, username: str, password: str, displayName: Optional[str]) -> Dict:
        clientsData = self.loadClients()
        
        if username in clientsData.get('clients', {}):
            return {"status": "error", "message": "пользователь уже существует"}
        
        clientsData['clients'][username] = {"password": password}
        self.saveClients(clientsData)
        
        userData = {
            "username": username,
            "display_name": displayName or username,
            "status": "offline",
            "chats": []
        }
        self.saveUser(username, userData, updateStatus=False)
        
        return {"status": "success", "message": "регистрация успешна"}
    
    #вход
    def handleLogin(self, username: str, password: str, clientSocket: locsoc.socket, address: Tuple[str, int]) -> Dict:
        if not self.authenticate(username, password):
            return {"status": "error", "message": "неверные данные"}
        
        if username in self.onlineUsers:
            return {"status": "error", "message": "пользователь уже онлайн"}
        
        userData = self.loadUser(username)
        if not userData:
            return {"status": "error", "message": "ошибка загрузки профиля"}
        
        session = ClientSession(username=username, socket=clientSocket, address=address)
        self.onlineUsers[username] = session
        
        userData['status'] = 'online'
        self.saveUser(username, userData, updateStatus=True)
        
        #уведомление
        self.broadcastUserStatus(username, 'online')
        
        return {
            "status": "success",
            "message": "вход успешен",
            "chats": userData.get('chats', [])
        }
    
    #выход
    def handleLogout(self, username: str):
        if username in self.onlineUsers:
            del self.onlineUsers[username]

            userData = self.loadUser(username)
            if userData:
                userData['status'] = 'offline'
                self.saveUser(username, userData, updateStatus=True)
            
            #уведомление
            self.broadcastUserStatus(username, 'offline')
    
    #отправить сообщение пользователю
    def sendToUser(self, username: str, message: Dict):
        if username in self.onlineUsers:
            try:
                session = self.onlineUsers[username]
                session.socket.send(json.dumps(message, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                print(f"ошибка отправки {username}: {e}")
    
    #разослать статус пользователя
    def broadcastUserStatus(self, username: str, status: str):
        message = {
            "type": "userStatus",
            "username": username,
            "status": status
        }
        for user in self.onlineUsers:
            if user != username:
                self.sendToUser(user, message)
    
    #отправить сообщение в чат
    def sendToChat(self, chatId: str, messageData: Dict) -> bool:
        if chatId not in self.chats:
            return False
        
        chatObj = self.chats[chatId]
        sender = messageData.get('sender')
        content = messageData.get('content')
        
        if not chatObj.canAccess(sender):
            return False
        
        chatObj.addMessage(sender, content)
        
        for participant in chatObj.participants:
            if participant != sender:
                self.sendToUser(participant, {
                    "type": "message",
                    "chatId": chatId,
                    "sender": sender,
                    "content": content,
                    "timestamp": messageData.get('timestamp', datetime.now().isoformat())
                })
        
        return True
    
    def getChatHistory(self, chatId: str) -> List[Dict]:
        if chatId not in self.chats:
            return []
        
        chatObj = self.chats[chatId]
        messages = chatObj.loadHistory()
        
        history = []
        for msg in messages:
            history.append({
                "sender": msg.sender,
                "content": msg.content,
                "timestamp": msg.timestamp
            })
        
        return history
    
    #создать новый чат
    def createChat(self, chatType: str, participants: List[str], creator: str, chatName: Optional[str]) -> str:
        if chatType == 'private' and len(participants) == 2:
            chatId = '_'.join(sorted(participants))
        else:
            chatId = chatName.lower().replace(' ', '_') if chatName else f"group_{int(datetime.now().timestamp())}"

        chatObj = chat.Chat(
            chatId=chatId,
            chatType=chatType,
            participants=participants,
            chatName=chatName,
            admin=creator
        )
        
        self.chats[chatId] = chatObj
        self.saveChats()
        
        for username in participants:
            userData = self.loadUser(username)
            if userData and chatId not in userData.get('chats', []):
                userData['chats'].append(chatId)
                self.saveUser(username, userData, updateStatus=False)
                
            if username in self.onlineUsers:
                self.sendToUser(username, {
                    "type": "chatCreated",
                    "chatId": chatId,
                    "chatName": chatName
                })
        
        return chatId
    
    #получить список онлайн
    def getOnlineList(self) -> List[str]:
        return list(self.onlineUsers.keys())
    
    #обработать запрос
    def handleRequest(self, clientSocket: locsoc.socket, address: Tuple[str, int]):
        try:
            while True:
                data = clientSocket.recv(4096)
                if not data:
                    break
                
                request = json.loads(data.decode('utf-8'))
                requestType = request.get('type')
                response = {"status": "error", "message": "неизвестный запрос"}
                
                if requestType == 'login':
                    response = self.handleLogin(
                        request['username'],
                        request['password'],
                        clientSocket,
                        address
                    )
                
                elif requestType == 'register':
                    response = self.handleRegister(
                        request['username'],
                        request['password'],
                        request.get('displayName')
                    )
                
                elif requestType == 'logout':
                    self.handleLogout(request['username'])
                    response = {"status": "success"}
                
                elif requestType == 'getOnline':
                    response = {
                        "type": "onlineList",
                        "users": self.getOnlineList()
                    }
                
                elif requestType == 'sendMessage':
                    success = self.sendToChat(
                        request['chatId'],
                        request
                    )
                    response = {
                        "status": "success" if success else "error",
                        "message": "отправлено" if success else "ошибка отправки"
                    }
                
                elif requestType == 'createChat':
                    chatId = self.createChat(
                        request['chatType'],
                        request['participants'],
                        request['creator'],
                        request.get('chatName')
                    )
                    response = {
                        "status": "success",
                        "chatId": chatId,
                        "message": "чат создан"
                    }
                
                elif requestType == 'getChatHistory':
                    chatId = request.get('chatId')
                    history = self.getChatHistory(chatId)
                    response = {
                        "type": "chatHistory",
                        "chatId": chatId,
                        "messages": history
                    }
                
                #отправить ответ
                clientSocket.send(json.dumps(response, ensure_ascii=False).encode('utf-8'))
        
        except json.JSONDecodeError:
            print(f"ошибка формата от {address}")
        except Exception as e:
            print(f"ошибка обработки {address}: {e}")
        finally:
            clientSocket.close()
    
    #при запуске сервера установить всех в offline
    def setAllUsersOffline(self):
        print("установка всех пользователей в офлайн...")
        
        try:
            if os.path.exists(self.usersDir):
                for filename in os.listdir(self.usersDir):
                    if filename.endswith('.json'):
                        username = filename[:-5]  # убрать .json
                        userPath = os.path.join(self.usersDir, filename)
                        try:
                            with open(userPath, 'r', encoding='utf-8') as f:
                                userData = json.load(f)
                            
                            #установить статус офлайн
                            userData['status'] = 'offline'
                            
                            with open(userPath, 'w', encoding='utf-8') as f:
                                json.dump(userData, f, ensure_ascii=False, indent=2)
                                
                            print(f"  {username} -> offline")
                        except Exception as e:
                            print(f"ошибка обновления {username}: {e}")
        except Exception as e:
            print(f"ошибка установки офлайн статуса: {e}")
    
    #запустить сервер
    def start(self):
        self.loadChats()
        self.setAllUsersOffline()
        
        try:
            self.serverSocket = locsoc.socket(locsoc.AF_INET, locsoc.SOCK_STREAM)
            self.serverSocket.bind((self.host, self.port))
            self.serverSocket.listen(5)
            self.running = True
            
            print(f"сервер запущен на {self.host}:{self.port}")
            print(f"загружено чатов: {len(self.chats)}")
            
            while self.running:
                try:
                    clientSocket, address = self.serverSocket.accept()
                    print(f"новое подключение от {address}")
                    
                    thread = threading.Thread(
                        target=self.handleRequest,
                        args=(clientSocket, address),
                        daemon=True
                    )
                    thread.start()
                
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"ошибка принятия подключения: {e}")
        
        except Exception as e:
            print(f"ошибка запуска сервера: {e}")
        finally:
            self.stop()
    
    #остановка
    def stop(self):
        for username in list(self.onlineUsers.keys()):
            self.handleLogout(username)
        
        self.running = False
        if self.serverSocket:
            self.serverSocket.close()
        print("сервер остановлен, все пользователи offline")

def main():
    server = Server()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nостановка сервера...")
    except Exception as e:
        print(f"ошибка: {e}")

if __name__ == "__main__":
    main()