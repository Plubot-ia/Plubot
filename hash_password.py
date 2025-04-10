import bcrypt

password = "plubot_password".encode('utf-8')
hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
print(hashed_password.decode('utf-8'))