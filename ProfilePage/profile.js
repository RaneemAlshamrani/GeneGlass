// Frontend-only profile preview. No authentication or database writes yet.
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
});
function setEditing(active) {
  editable.forEach((input) => (input.disabled = !active));
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
  editable.forEach((input, i) => (input.value = original[i]));
  message.textContent = "";
  setEditing(false);
});
form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  document.getElementById("displayName").textContent = editable[0].value.trim();
  setEditing(false);
  message.textContent =
    "Preview updated. Changes are not saved to the database yet.";
});
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
