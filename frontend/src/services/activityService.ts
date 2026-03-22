/**
 * Service for managing activity feed operations.
 */

import { Activity } from "@/types";
import { apiClient } from "@/services/apiClient";

class ActivityService {
  /**
   */
  async getRecentActivities(limit: number = 10): Promise<Activity[]> {
    return apiClient.getJson<Activity[]>(`/api/activities?limit=${encodeURIComponent(limit)}`);
  }

  /**
   * Get activities for a specific document
   */
  async getDocumentActivities(documentId: string): Promise<Activity[]> {
    return apiClient.getJson<Activity[]>(`/api/documents/${encodeURIComponent(documentId)}/activities`);
  }

  /**
   * Get activities by user
   */
  async getUserActivities(userName: string): Promise<Activity[]> {
    return apiClient.getJson<Activity[]>(`/api/activities?user=${encodeURIComponent(userName)}&limit=100`);
  }

  /**
   * Add new activity
   */
  async addActivity(activity: Omit<Activity, "id" | "time">): Promise<Activity> {
    return apiClient.postJson<Activity>("/api/activities", activity);
  }
}

// Export singleton instance
export const activityService = new ActivityService();
