class UserList:
    """Wrapper around the 'currently connected users' dictionary"""

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

    def itsme(self, user_id):
        return self.my_id == user_id

    @property
    def my_name(self):
        return self.name(self.my_id)