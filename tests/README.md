\# Test Suite Overview



\## Test Files



| Test File                  | What It Tests                                                      |

|----------------------------|--------------------------------------------------------------------|

| tests/conftest.py          | Sets up app, test client, database, and helper tokens             |

| tests/test\_auth.py         | Login/logout, wrong password, missing fields, token expiry        |

| tests/test\_user.py         | User registration, profile updates/deletes, duplicate email/username, 403 errors |

| tests/test\_project.py      | Project create/read/update/delete, ownership checks, cache clearing |

| tests/test\_experience.py   | Experience create/update/delete, date checks, access control      |

| tests/test\_verification.py | Create verification requests, email mock, token response, expired tokens |

| tests/test\_share.py        | Create share links, public access, view count, expiry checks      |

| tests/test\_coverage.py     | Test coverage for all modules                                      |



---



\## Bugs Identified and Fixed



| Problem                     | What Happened                                               | How It Was Fixed                                  |

|------------------------------|-------------------------------------------------------------|--------------------------------------------------|

| Date order bug               | End date could be before start date                         | Added a check to make sure dates are correct    |

| Token expiry not enforced    | Expired tokens were still accepted                           | Added a check for token expiry                  |

| 403 vs 404 confusion         | Accessing another user's data returned 404 instead of 403   | Changed logic to return 403 for unauthorized   |

| Duplicate registration error | Duplicate email/username caused a 500 error                 | Added proper error handling to return 409       |

| Cache not updated after delete | Deleted projects were still shown from cache               | Cleared cache after updates and deletes        |

