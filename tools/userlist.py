class UserList:
    """Wrapper around the 'currently connected users' dictionary"""
    COLOR_COUNT = 56

    def __init__(self, userlist_data):
        self.users = {user_data["userid"]: user_data for user_data in userlist_data}
        for id, user in self.users.items():
            if "you" in user["params"] and user["params"]["you"]:
                self.my_id = id

    def del_user(self, user_id):
        del self.users[user_id]

    def add_user(self, user_id, params):
        self.users[user_id] = {"params": params}

    def __getitem__(self, item : str):
        return self.users[item]["params"]

    def name(self, user_id):
        return self.users[user_id]["params"]["name"]

    def color(self, user_id):
        return int(user_id, 16) % 56 + 1

    def itsme(self, user_id):
        return self.my_id == user_id

    @property
    def my_name(self):
        return self.name(self.my_id)