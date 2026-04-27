import { Activity } from "@/types";
import { apiClient } from "@/services/apiClient";

class ActivityService {

  async getRecentActivities(limit: number = 10): Promise<Activity[]> {
    return apiClient.getJson<Activity[]>(`/api/activities?limit=${encodeURIComponent(limit)}`, { requireAuth: true });
  }

  //Get activities for a specific document

  async getDocumentActivities(documentId: string): Promise<Activity[]> {
    return apiClient.getJson<Activity[]>(`/api/documents/${encodeURIComponent(documentId)}/activities`, { requireAuth: true });
  }


  // Get activities by user

  async getUserActivities(userName: string): Promise<Activity[]> {
    return apiClient.getJson<Activity[]>(`/api/activities?user=${encodeURIComponent(userName)}&limit=100`, { requireAuth: true });
  }

  //Add new activity

  async addActivity(activity: Omit<Activity, "id" | "time">): Promise<Activity> {
    return apiClient.postJson<Activity>("/api/activities", activity, { requireAuth: true });
  }
}

// Export singleton instance
export const activityService = new ActivityService();
