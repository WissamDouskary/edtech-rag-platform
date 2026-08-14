import axios from "axios";
import apiClient from "./client";

export async function listDocuments() {
  const { data } = await apiClient.get("/documents/");
  return data;
}

export async function requestUploadUrl({ filename, contentType, sizeBytes }) {
  const { data } = await apiClient.post("/documents/upload-url/", {
    filename,
    content_type: contentType,
    size_bytes: sizeBytes,
  });
  return data;
}

export async function uploadFileToStorage(uploadUrl, file, contentType, onProgress) {
  await axios.put(uploadUrl, file, {
    headers: { "Content-Type": contentType },
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) {
        onProgress(Math.round((evt.loaded / evt.total) * 100));
      }
    },
  });
}

export async function confirmUpload({ storageKey, filename }) {
  const { data } = await apiClient.post("/documents/confirm/", {
    storage_key: storageKey,
    filename,
  });
  return data;
}

export async function renameDocument(id, filename) {
  const { data } = await apiClient.patch(`/documents/${id}/`, { filename });
  return data;
}

export async function deleteDocument(id) {
  await apiClient.delete(`/documents/${id}/`);
}

export async function retryDocument(id) {
  const { data } = await apiClient.post(`/documents/${id}/retry/`);
  return data;
}

export async function uploadDocument(file, onProgress) {
  const { upload_url: uploadUrl, storage_key: storageKey, content_type: contentType } =
    await requestUploadUrl({
      filename: file.name,
      contentType: file.type || "application/pdf",
      sizeBytes: file.size,
    });

  await uploadFileToStorage(uploadUrl, file, contentType, onProgress);

  return confirmUpload({ storageKey, filename: file.name });
}
