const ACCESS_TOKEN_KEY = 'gart.access_token';
const USER_KEY = 'gart.user';

export function clearAuthSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export async function getCurrentUser() {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY);
  if (!token) return null;

  const response = await fetch('/api/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`No se pudo validar la sesión (${response.status}).`);
  }

  const session = await response.json();
  if (!session.authenticated || !session.user) {
    clearAuthSession();
    return null;
  }

  localStorage.setItem(USER_KEY, JSON.stringify(session.user));
  return session.user;
}

export async function logout() {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY);
  if (token) {
    const response = await fetch('/api/auth/logout', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      throw new Error(`No se pudo cerrar la sesión (${response.status}).`);
    }
  }

  clearAuthSession();
}

export function initializeAuthNavigation() {
  const authLink = document.querySelector('[data-auth-link]');
  if (!authLink) return;

  authLink.addEventListener('click', async (event) => {
    if (!localStorage.getItem(ACCESS_TOKEN_KEY)) return;

    event.preventDefault();
    authLink.setAttribute('aria-busy', 'true');
    try {
      await logout();
      window.location.assign('/login');
    } catch (error) {
      console.error('No se pudo cerrar la sesión.', error);
      window.alert('No se pudo cerrar la sesión. Comprueba tu conexión e inténtalo de nuevo.');
    } finally {
      authLink.removeAttribute('aria-busy');
    }
  });

  getCurrentUser()
    .then((user) => {
      if (!user) return;
      authLink.textContent = 'Cerrar sesión';
      authLink.href = '/login';
      authLink.setAttribute('aria-label', `Cerrar sesión de ${user.username}`);
    })
    .catch((error) => console.error('No se pudo validar la sesión.', error));
}
