# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from pydantic import BaseModel


class TestUserProfile(BaseModel):
    __test__ = False  # prevent pytest from treating this as a test case

    username: str
    email: str
    first_name: str
    last_name: str
    sex: str
    idp_user_id: str


def get_test_user_profiles() -> list[TestUserProfile]:
    profiles: list[TestUserProfile] = []
    last_names = ["Example", "Tester", "Sample"]

    for index in range(1, 121):
        profiles.append(
            TestUserProfile(
                username=f"user{index}",
                email=f"user{index}@example.com",
                first_name=f"Test{index}",
                last_name=last_names[(index - 1) % len(last_names)],
                sex="F" if index % 2 == 0 else "M",
                idp_user_id=str(index),
            )
        )

    return profiles


TEST_PROFILES = get_test_user_profiles()
