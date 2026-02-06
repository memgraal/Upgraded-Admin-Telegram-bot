from sqlalchemy_manager.pagination import AsyncPaginator


class UserGroupPaginator(AsyncPaginator):
    per_page = 4
