(() => {
  const tokenKey = "geneglass_access_token";
  const userKey = "geneglass_user";

  function findStoredSession() {
    for (const storage of [sessionStorage, localStorage]) {
      const token = storage.getItem(tokenKey);
      if (token) return { storage, token };
    }
    return null;
  }

  function clearSession() {
    for (const storage of [sessionStorage, localStorage]) {
      storage.removeItem(tokenKey);
      storage.removeItem(userKey);
    }
  }

  function redirectToLogin() {
    window.location.replace("../LoginPage/login.html");
  }

  function updateUserInterface(user) {
    document.querySelectorAll("[data-auth-name]").forEach((element) => {
      element.textContent = user.full_name;
    });
    document.querySelectorAll("[data-auth-email]").forEach((element) => {
      if ("value" in element) element.value = user.email;
      else element.textContent = user.email;
    });
    document.querySelectorAll("[data-auth-department]").forEach((element) => {
      const department = user.department || "Not provided";
      if ("value" in element) element.value = department;
      else element.textContent = department;
    });
    document.querySelectorAll("[data-auth-greeting]").forEach((element) => {
      element.textContent = `Hi, ${user.full_name}`;
    });
  }

  async function verifySession() {
    const storedSession = findStoredSession();
    if (!storedSession) {
      redirectToLogin();
      return;
    }

    try {
      const response = await fetch(
        `${window.GeneGlassConfig.apiBaseUrl}/auth/me`,
        {
          headers: { Authorization: `Bearer ${storedSession.token}` },
        },
      );
      if (!response.ok) throw new Error("Session is no longer valid");

      const user = await response.json();
      storedSession.storage.setItem(userKey, JSON.stringify(user));
      updateUserInterface(user);
      window.GeneGlassAuth = {
        token: storedSession.token,
        user,
        logout() {
          clearSession();
          redirectToLogin();
        },
      };
      document.dispatchEvent(
        new CustomEvent("geneglass:auth-ready", { detail: user }),
      );
    } catch (_error) {
      clearSession();
      redirectToLogin();
    }
  }

  verifySession();
})();
