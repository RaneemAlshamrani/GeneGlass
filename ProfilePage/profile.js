const form = document.getElementById("profileForm");
const editBtn = document.getElementById("editBtn");
const cancelBtn = document.getElementById("cancelBtn");
const editActions = document.getElementById("editActions");
const message = document.getElementById("profileMessage");

const editable = ["fullName", "email", "department"].map((id) =>
  document.getElementById(id),
);

let original = editable.map((input) => input.value);

document.addEventListener("geneglass:auth-ready", () => {
  original = editable.map((input) => input.value);
  loadProfileStatistics();
});

function setEditing(active) {
  editable.forEach((input) => {
    input.disabled = !active;
  });

  editActions.hidden = !active;
  editBtn.hidden = active;

  if (active) editable[0].focus();
}

editBtn.addEventListener("click", () => {
  original = editable.map((input) => input.value);
  message.textContent = "";
  setEditing(true);
});

cancelBtn.addEventListener("click", () => {
  editable.forEach((input, index) => {
    input.value = original[index];
  });

  message.textContent = "";
  setEditing(false);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!form.reportValidity()) return;

  const token = window.GeneGlassAuth?.token;

  if (!token) {
    message.textContent =
      "Your session has expired. Please log in again.";
    return;
  }

  const saveBtn = form.querySelector('[type="submit"]');

  if (saveBtn) saveBtn.disabled = true;
  message.textContent = "Saving...";

  try {
    const response = await fetch(
      `${window.GeneGlassConfig.apiBaseUrl}/users/me`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          full_name: editable[0].value.trim(),
          email: editable[1].value.trim(),
          department: editable[2].value.trim() || null,
        }),
      },
    );

    const result = await response.json();

    if (!response.ok) {
      let errorMessage = "Could not save your profile.";

      if (typeof result.detail === "string") {
        errorMessage = result.detail;
      } else if (response.status === 422) {
        errorMessage = "Please check your profile information.";
      }

      throw new Error(errorMessage);
    }

    editable[0].value = result.full_name;
    editable[1].value = result.email;
    editable[2].value = result.department || "";

    document.querySelectorAll("[data-auth-name]").forEach((element) => {
      if ("value" in element) {
        element.value = result.full_name;
      } else {
        element.textContent = result.full_name;
      }
    });

    document.querySelectorAll("[data-auth-email]").forEach((element) => {
      if ("value" in element) {
        element.value = result.email;
      } else {
        element.textContent = result.email;
      }
    });

    document.querySelectorAll("[data-auth-department]").forEach((element) => {
      const department = result.department || "Not provided";

      if ("value" in element) {
        element.value = department;
      } else {
        element.textContent = department;
      }
    });

    if (window.GeneGlassAuth) {
      window.GeneGlassAuth.user = {
        ...window.GeneGlassAuth.user,
        ...result,
      };

      const updatedUser = JSON.stringify(window.GeneGlassAuth.user);

      for (const storage of [sessionStorage, localStorage]) {
        if (storage.getItem("geneglass_access_token")) {
          storage.setItem("geneglass_user", updatedUser);
        }
      }
    }

    original = editable.map((input) => input.value);
    setEditing(false);
    message.textContent = "Profile updated successfully!";
  } catch (error) {
    message.textContent =
      error.message || "Something went wrong. Please try again.";
  } finally {
    if (saveBtn) saveBtn.disabled = false;
  }
});

async function loadProfileStatistics() {
  const statisticsMessage =
    document.getElementById("statisticsMessage");
  const totalCount = document.getElementById("totalCount");
  const completedCount = document.getElementById("completedCount");
  const reviewCount = document.getElementById("reviewCount");

  const token = window.GeneGlassAuth?.token;

  if (!token) {
    statisticsMessage.textContent =
      "Please log in to view your statistics.";
    return;
  }

  statisticsMessage.textContent = "Loading your analysis statistics...";

  try {
    const response = await fetch(
      `${window.GeneGlassConfig.apiBaseUrl}/users/me/statistics`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    const result = await response.json();

    if (!response.ok) {
      throw new Error(
        result.detail || "Could not load statistics.",
      );
    }

    totalCount.textContent = result.total_analyses;
    completedCount.textContent = result.completed_analyses;
    reviewCount.textContent = result.needs_review;

    statisticsMessage.textContent = "Statistics are up to date.";
  } catch (error) {
    statisticsMessage.textContent =
      error.message || "Could not load your analysis statistics.";
  }
}

document.getElementById("logoutBtn").addEventListener("click", () => {
  if (window.GeneGlassAuth) {
    window.GeneGlassAuth.logout();
    return;
  }

  sessionStorage.removeItem("geneglass_access_token");
  sessionStorage.removeItem("geneglass_user");
  localStorage.removeItem("geneglass_access_token");
  localStorage.removeItem("geneglass_user");

  window.location.replace("../LoginPage/login.html");
});

const passwordForm = document.getElementById("changePasswordForm");
const passwordMessage = document.getElementById("passwordMessage");
const changePasswordBtn = document.getElementById("changePasswordBtn");

passwordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  passwordMessage.textContent = "";

  const currentPassword =
    document.getElementById("currentPassword").value;
  const newPassword =
    document.getElementById("newPassword").value;
  const confirmPassword =
    document.getElementById("confirmPassword").value;

  if (newPassword !== confirmPassword) {
    passwordMessage.textContent = "New passwords do not match.";
    return;
  }

  if (newPassword.length < 12) {
    passwordMessage.textContent =
      "New password must be at least 12 characters.";
    return;
  }

  const token = window.GeneGlassAuth?.token;

  if (!token) {
    passwordMessage.textContent =
      "Your session has expired. Please log in again.";
    return;
  }

  changePasswordBtn.disabled = true;
  passwordMessage.textContent = "Changing password...";

  try {
    const response = await fetch(
      `${window.GeneGlassConfig.apiBaseUrl}/auth/change-password`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      },
    );

    const result = await response.json();

    if (!response.ok) {
      throw new Error(
        result.detail || "Could not change the password.",
      );
    }

    passwordMessage.textContent = "Password changed successfully.";
    passwordForm.reset();
  } catch (error) {
    passwordMessage.textContent =
      error.message || "Something went wrong. Please try again.";
  } finally {
    changePasswordBtn.disabled = false;
  }
});