import apiClient from "./client";

export async function registerUser({ email, password, password2, firstName, lastName }) {
  const { data } = await apiClient.post("/auth/register/", {
    email,
    password,
    password2,
    first_name: firstName,
    last_name: lastName,
  });
  return data;
}

export async function loginUser({ email, password }) {
  const { data } = await apiClient.post("/auth/login/", { email, password });
  return data;
}

export async function fetchCurrentUser() {
  const { data } = await apiClient.get("/auth/me/");
  return data;
}
