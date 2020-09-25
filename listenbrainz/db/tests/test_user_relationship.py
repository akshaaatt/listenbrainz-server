# listenbrainz-server - Server for the ListenBrainz project.
#
# Copyright (C) 2020 Param Singh <iliekcomputers@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

from listenbrainz import db
from listenbrainz.db.testing import DatabaseTestCase
from listenbrainz.db.exceptions import DatabaseException

import listenbrainz.db.user as db_user
import listenbrainz.db.user_relationship as db_user_relationship


class UserRelationshipTestCase(DatabaseTestCase):
    def setUp(self):
        super(UserRelationshipTestCase, self).setUp()
        self.main_user = db_user.get_or_create(1, 'iliekcomputers')
        self.followed_user_1 = db_user.get_or_create(2, 'followed_user_1')

    def test_insert(self):
        db_user_relationship.insert(self.main_user['id'], self.followed_user_1['id'], 'follow')
        self.assertTrue(db_user_relationship.is_following_user(self.main_user['id'], self.followed_user_1['id']))

    def test_insert_raises_value_error_for_invalid_relationship(self):
        with self.assertRaises(ValueError):
            db_user_relationship.insert(self.main_user['id'], self.followed_user_1['id'], 'idkwhatrelationshipthisis')

    def test_is_following_user(self):
        self.assertFalse(db_user_relationship.is_following_user(self.main_user['id'], self.followed_user_1['id']))
        db_user_relationship.insert(self.main_user['id'], self.followed_user_1['id'], 'follow')
        self.assertTrue(db_user_relationship.is_following_user(self.main_user['id'], self.followed_user_1['id']))

    def test_delete(self):
        db_user_relationship.insert(self.main_user['id'], self.followed_user_1['id'], 'follow')
        self.assertTrue(db_user_relationship.is_following_user(self.main_user['id'], self.followed_user_1['id']))
        db_user_relationship.delete(self.main_user['id'], self.followed_user_1['id'], 'follow')
        self.assertFalse(db_user_relationship.is_following_user(self.main_user['id'], self.followed_user_1['id']))

    def test_delete_raises_value_error_for_invalid_relationships(self):
        with self.assertRaises(ValueError):
            db_user_relationship.delete(self.main_user['id'], self.followed_user_1['id'], 'idkwhatrelationshipthisis')

    def test_get_followers_of_user_returns_correct_data(self):
        # no relationships yet, should return an empty list
        followers = db_user_relationship.get_followers_of_user(self.followed_user_1['id'])
        self.assertListEqual(followers, [])

        # add two relationships
        db_user_relationship.insert(self.main_user['id'], self.followed_user_1['id'], 'follow')
        self.following_user_1 = db_user.get_or_create(3, 'following_user_1')
        db_user_relationship.insert(self.following_user_1['id'], self.followed_user_1['id'], 'follow')

        # At this point, the main_user and following_user_1 follow followed_user_1
        # So, if we get the followers of followed_user_1, we'll get back two users
        followers = db_user_relationship.get_followers_of_user(self.followed_user_1['id'])
        self.assertEqual(2, len(followers))

    def test_get_following_for_user_returns_correct_data(self):

        # no relationships yet, should return an empty list
        following = db_user_relationship.get_following_for_user(self.main_user['id'])
        self.assertListEqual(following, [])

        # make the main_user follow followed_user_1
        db_user_relationship.insert(self.main_user['id'], self.followed_user_1['id'], 'follow')

        # the list of users main_user is following should have 1 element now
        following = db_user_relationship.get_following_for_user(self.main_user['id'])
        self.assertEqual(1, len(following))

        # make it so that the main user follows two users, followed_user_1 and followed_user_2
        self.followed_user_2 = db_user.get_or_create(3, 'followed_user_2')
        db_user_relationship.insert(self.main_user['id'], self.followed_user_2['id'], 'follow')

        # the list of users main_user is following should have 2 elements now
        following = db_user_relationship.get_following_for_user(self.main_user['id'])
        self.assertEqual(2, len(following))
