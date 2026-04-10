import logging
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.models.schemas import UserCreate, TokenResponse, UserResponse
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_registrar
)
from app.database import get_connection, return_connection, get_db_cursor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(
    user: UserCreate,
    current_user: dict = Depends(require_registrar)
) -> UserResponse:
    """
    Creates a new user account with hashed password.
    Only the registrar or admin should call this in production.
    Role is validated by UserCreate schema before reaching this function.

    Parameters:
        user (UserCreate): Request body with email, password, and role
        current_user (dict): The authenticated registrar performing the action

    Returns:
        UserResponse: Created user data excluding password

    Raises:
        HTTPException 400: If email already exists
    """
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        hashed = hash_password(user.password)

        cursor.execute(
            """
            INSERT INTO users (email, password_hash, role)
            VALUES (%s, %s, %s)
            RETURNING id, email, role, created_at
        """,
            (user.email, hashed, user.role),
        )

        conn.commit()
        new_user = dict(cursor.fetchone())
        logger.info(f"Registrar {current_user['email']} created new user: {user.email} with role: {user.role}")
        return new_user

    except HTTPException:
        raise

    except Exception as e:
        conn.rollback()
        logger.error(f"Registration error for {user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )

    finally:
        cursor.close()
        return_connection(conn)


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """
    Authenticates a user and returns a JWT token containing email and role.
    Uses OAuth2PasswordRequestForm so Swagger Authorize button works correctly.
    Role is embedded in the token so every subsequent request carries permissions.

    Parameters:
        form_data: OAuth2 form with username (email) and password fields

    Returns:
        TokenResponse: JWT token, token type, and user role

    Raises:
        HTTPException 401: If credentials are invalid
    """
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
        cursor.execute(
            "SELECT id, email, password_hash, role FROM users WHERE email = %s",
            (form_data.username,),
        )
        db_user = cursor.fetchone()

        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not verify_password(form_data.password, db_user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        token = create_access_token(
            data={"sub": db_user["email"], "role": db_user["role"]}
        )

        logger.info(f"User logged in: {db_user['email']} role: {db_user['role']}")

        return {"access_token": token, "token_type": "bearer", "role": db_user["role"]}

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
        )

    finally:
        cursor.close()
        return_connection(conn)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    """
    Returns the authenticated user's profile.
    Protected — requires valid JWT token.

    Parameters:
        current_user (dict): Injected by Depends(get_current_user)

    Returns:
        UserResponse: User data excluding password
    """
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
        cursor.execute(
            "SELECT id, email, role, created_at FROM users WHERE email = %s",
            (current_user["email"],),
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return dict(user)
    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch profile",
        )

    finally:
        cursor.close()
        return_connection(conn)
