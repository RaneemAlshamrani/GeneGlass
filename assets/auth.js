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
  document.querySelectorAll("[data-auth-name]").forEach((el) => {
    if ("value" in el) {
      el.value = user.full_name;
    } else {
      el.textContent = user.full_name;
    }
  });

  document.querySelectorAll("[data-auth-email]").forEach((el) => {
    if ("value" in el) {
      el.value = user.email;
    } else {
      el.textContent = user.email;
    }
  });

  document.querySelectorAll("[data-auth-department]").forEach((el) => {
    const department = user.department || "Not provided";

    if ("value" in el) {
      el.value = department;
    } else {
      el.textContent = department;
    }
  });

  document.querySelectorAll("[data-auth-greeting]").forEach((el) => {
    el.textContent = `Hi, ${user.full_name}`;
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
