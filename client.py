import socket as locsoc
import json
import threading
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class Client:
    username: str
    host: str = 'localhost'
    port: int = 8888
    socket: Optional[locsoc.socket] = None
    running: bool = False
    currentChat: Optional[str] = None
    userChats: List[str] = field(default_factory=list)
    
    #подключиться к серверу
    def connect(self):
        try:
            self.socket = locsoc.socket(locsoc.AF_INET, locsoc.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"[{self.username}] подключен к {self.host}:{self.port}")
            return True
        except ConnectionRefusedError:
            print(f"[{self.username}] сервер недоступен")
            return False
        except Exception as e:
            print(f"[{self.username}] ошибка: {e}")
            return False
    
    #отправить данные
    def send(self, data):
        try:
            json_data = json.dumps(data, ensure_ascii=False)
            self.socket.send(json_data.encode('utf-8'))
        except Exception as e:
            print(f"[{self.username}] ошибка отправки: {e}")
    
    #получить ответ
    def receive(self, timeout=5):
        try:
            self.socket.settimeout(timeout)
            data = self.socket.recv(4096)
            if data:
                return json.loads(data.decode('utf-8'))
        except locsoc.timeout:
            return None
        except Exception as e:
            print(f"[{self.username}] ошибка получения: {e}")
            return None
        finally:
            self.socket.settimeout(None)
    
    #войти в систему
    def login(self, password):
        authData = {
            'type': 'login',
            'username': self.username,
            'password': password
        }
        self.send(authData)
        response = self.receive()
        if response and response.get('status') == 'success':
            self.userChats = response.get('chats', [])
            print(f"[{self.username}] авторизован")
            return True
        error = response.get('message', 'ошибка') if response else 'нет ответа'
        print(f"[{self.username}] ошибка: {error}")
        return False
    
    #регистрация
    def register(self, password, displayName=None):
        regData = {
            'type': 'register',
            'username': self.username,
            'password': password,
            'displayName': displayName or self.username
        }
        self.send(regData)
        response = self.receive()
        if response and response.get('status') == 'success':
            print(f"[{self.username}] зарегистрирован")
            return True
        error = response.get('message', 'ошибка') if response else 'нет ответа'
        print(f"[{self.username}] ошибка: {error}")
        return False
    
    #кто онлайн
    def getOnline(self):
        self.send({'type': 'getOnline'})
    
    #создать чат
    def createChat(self, chatType, participants, chatName=None):
        if self.username not in participants:
            participants.append(self.username)
        request = {
            'type': 'createChat',
            'chatType': chatType,
            'participants': participants,
            'creator': self.username
        }
        if chatName:
            request['chatName'] = chatName
        self.send(request)
    
    #отправить сообщение
    def sendMessage(self, chatId, content):
        message = {
            'type': 'sendMessage',
            'chatId': chatId,
            'sender': self.username,
            'content': content,
            'timestamp': datetime.now().isoformat()
        }
        self.send(message)
    
    #выбрать чат с показом истории
    def selectChat(self, chatId):
        if chatId in self.userChats:
            self.currentChat = chatId
            print(f"\n[{self.username}] выбран чат {chatId}")
            
            request = {'type': 'getChatHistory', 'chatId': chatId}
            self.send(request)
            
        else:
            print(f"[{self.username}] нет доступа к {chatId}")
    
    #выйти из системы
    def logout(self):
        if self.socket:
            self.send({'type': 'logout', 'username': self.username})
            self.running = False
            self.socket.close()
        print(f"[{self.username}] вышел")
    
    #обрабатывать сообщения от сервера
    def handleServerMessage(self, message):
        msgType = message.get('type')
        
        if msgType == 'message':
            chatId = message.get('chatId')
            sender = message.get('sender')
            content = message.get('content')
            print(f"\n[{chatId}] {sender}: {content}")
            if self.running:
                print(f"{self.username}> ", end='', flush=True)
            
        elif msgType == 'userStatus':
            user = message.get('username')
            status = message.get('status')
            print(f"\n[система] {user} теперь {status}")
            if self.running:
                print(f"{self.username}> ", end='', flush=True)
            
        elif msgType == 'onlineList':
            users = message.get('users', [])
            print(f"\n[система] онлайн: {', '.join(users)}")
            if self.running:
                print(f"{self.username}> ", end='', flush=True)
            
        elif msgType == 'chatCreated':
            chatId = message.get('chatId')
            chatName = message.get('chatName', chatId)
            self.userChats.append(chatId)
            print(f"\n[система] добавлен в чат: {chatName}")
            if self.running:
                print(f"{self.username}> ", end='', flush=True)
            
        elif msgType == 'error':
            error = message.get('message', 'ошибка')
            print(f"\n[ошибка] {error}")
            if self.running:
                print(f"{self.username}> ", end='', flush=True)
        
        elif msgType == 'chatHistory':
            #показать историю при выборе чата
            chatId = message.get('chatId')
            messages = message.get('messages', [])
            
            print(f"\n--- История чата: {chatId} ---")
            if messages:
                for msg in messages:
                    sender = msg.get('sender', 'неизвестно')
                    content = msg.get('content', '')
                    timestamp = msg.get('timestamp', '')
                    #time_str = datetime.fromisoformat(timestamp).strftime("%H:%M")
                    print(f"{sender}: {content}")
            else:
                print("(нет сообщений)")
            print("---" * 15)
            
            if self.running:
                print(f"{self.username} [{chatId}]> ", end='', flush=True)
    
    #слушать сообщения от сервера
    def listenMessages(self):
        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    print(f"[{self.username}] соединение разорвано")
                    break
                message = json.loads(data.decode('utf-8'))
                self.handleServerMessage(message)
            except ConnectionResetError:
                print(f"[{self.username}] сервер отключился")
                break
            except json.JSONDecodeError:
                print(f"[{self.username}] ошибка формата")
            except Exception as e:
                if self.running:
                    print(f"[{self.username}] ошибка: {e}")
                break
    
    #обрабатывать команды
    def handleCommand(self, cmd):
        parts = cmd.split()
        cmdType = parts[0].lower()
        
        if cmdType == '/exit':
            self.running = False
            
        elif cmdType == '/online':
            self.getOnline()
            
        elif cmdType == '/chats':
            if self.userChats:
                print("ваши чаты:")
                for i, chat in enumerate(self.userChats, 1):
                    print(f"  {i}. {chat}")
            else:
                print("нет чатов")
                
        elif cmdType == '/select' and len(parts) > 1:
            self.selectChat(parts[1])
            
        elif cmdType == '/private' and len(parts) > 1:
            self.createChat('private', [parts[1]])
            
        elif cmdType == '/group' and len(parts) > 2:
            users = parts[1].split(',')
            name = ' '.join(parts[2:])
            self.createChat('group', users, name)
            
        elif cmdType == '/msg' and len(parts) > 1:
            if self.currentChat:
                message_text = ' '.join(parts[1:])
                print(f"[{self.username}] -> {self.currentChat}: {message_text}")
                self.sendMessage(self.currentChat, message_text)
            else:
                print("сначала выберите чат: /select <chat_id>")
                
        elif cmdType == '/help':
            print("команды:")
            print("  /online - кто онлайн")
            print("  /chats - мои чаты")
            print("  /select <chat_id> - выбрать чат и показать историю")
            print("  /private <user> - создать личный чат")
            print("  /group <user1,user2,...> <name> - создать групповой чат")
            print("  /msg <текст> - отправить сообщение в выбранный чат")
            print("  /exit - выход")
        else:
            print(f"неизвестная команда: {cmdType}")
    
    #запуск
    def run(self):
        if not self.connect():
            return
        
        print(f"\nпользователь: {self.username}")
        print("новый пользователь? (y/n): ", end='')
        isNew = input().strip().lower()
        
        if isNew == 'y':
            password = input("пароль: ").strip()
            displayName = input("отображаемое имя (опционально): ").strip() or None
            if not self.register(password, displayName):
                return
        else:
            password = input("пароль: ").strip()
            if not self.login(password):
                return
        
        self.running = True
        thread = threading.Thread(target=self.listenMessages, daemon=True)
        thread.start()
        
        print(f"\n{self.username} в сети")
        print("/help для списка команд")
        print("-" * 40)
        
        try:
            while self.running:
                prompt = f"{self.username}"
                if self.currentChat:
                    prompt += f" [{self.currentChat}]"
                prompt += "> "
                
                try:
                    userInput = input(prompt).strip()
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\nпрервано")
                    break
                
                if not userInput:
                    continue
                
                if userInput.startswith('/'):
                    self.handleCommand(userInput)
                elif self.currentChat:
                    #отправка обычного сообщения
                    self.sendMessage(self.currentChat, userInput)
                else:
                    print("сначала выберите чат: /select <chat_id>")
        except KeyboardInterrupt:
            print("\nзавершение...")
        finally:
            self.logout()

def main():
    if len(sys.argv) != 2:
        print("использование: python client.py <имя_пользователя>")
        print("пример: python client.py saccharok")
        return
    
    client = Client(sys.argv[1])
    try:
        client.run()
    except KeyboardInterrupt:
        print("\nклиент завершен")
    except Exception as e:
        print(f"ошибка: {e}")

if __name__ == "__main__":
    main()