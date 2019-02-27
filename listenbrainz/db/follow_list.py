import sqlalchemy
from listenbrainz import db

def _create(connection, name, creator, private=False):
    result = connection.execute(sqlalchemy.text("""
        INSERT INTO follow_list (name, creator, private)
             VALUES (:name, :creator, :private)
          RETURNING id
    """), {
        'name': name,
        'creator': user_id,
        'private': private,
    })
    return result.fetchone()['id']


def _add_users(connection, list_id, user_ids):
    connection.execute(sqlalchemy.text("""
        INSERT INTO follow_list_member (list_id, user_id)
             VALUES (:list_id, :user_id)
    """), [{'list_id': list_id, 'user_id': user_id} for user_id in user_ids])


def _remove_users(connection, list_id, user_ids):
    connection.execute(sqlalchemy.text("""
        DELETE FROM follow_list_member (list_id, user_id)
              WHERE list_id = :list_id
                AND user_id IN :user_ids
    """), {'list_id': list_id, 'user_ids': tuple(user_ids))


def _get_members(connection, list_id):
    result = connection.execute(sqlalchemy.text("""
        SELECT user_id, musicbrainz_id, created
          FROM follow_list_member
          JOIN "user"
            ON follow_list_member.user_id = "user".id
         WHERE list_id = :list_id
    """), {
        'list_id': list_id,
    })
    return [dict(row) for row in result.fetchall()]


def _get_by_creator_and_name(connection, creator, list_name):
    r = connection.execute(sqlalchemy.text("""
        SELECT id
          FROM follow_list
         WHERE creator = :creator
           AND LOWER(name) = LOWER(:list_name)
    """), {
        'creator': creator,
        'list_name': list_name,
    })

    if r.rowcount > 0:
        return r.fetchone()['id']
    else:
        return None


def save(name, creator, members, private=False):
    with db.engine.begin() as connection:
        list_id = _get_by_creator_and_name(connection, creator, name)
        if not list_id:
            list_id = _create(connection, name, creator, private)

        old_members = set(member['user_id'] for member in _get_members(connection, list_id))
        members = set(members)
        users_to_add = members - old_members
        users_to_remove = old_list - members
        _add_users(connection, list_id, users_to_add)
        _remove_users(connection, list_id, users_to_remove)

    return list_id


def get_follow_lists(user_id):
    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text("""
            SELECT id, name, creator, private
              FROM follow_list
             WHERE user_id = :user_id
        """), {
            'user_id': user_id,
        })
        return [dict(row) for row in result.fetchall()]
