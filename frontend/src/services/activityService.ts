/**
 * Service for managing activity feed operations.
 */

import { Activity } from "@/types";
import { mockActivities } from "@/data/mock-documents";

class ActivityService {
  /**
   */
  async getRecentActivities(limit: number = 10): Promise<Activity[]> {
    try {
      const response = await fetch(`/api/activities?limit=${limit}`);
      if (!response.ok) throw new Error(`Failed to fetch activities: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn("Falling back to mock activities (recent):", error);
      return mockActivities.slice(0, limit);
    }
  }

  /**
   * Get activities for a specific document
   */
  async getDocumentActivities(documentId: string): Promise<Activity[]> {
    try {
      const response = await fetch(`/api/documents/${encodeURIComponent(documentId)}/activities`);
      if (!response.ok) throw new Error(`Failed to fetch document activities: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn("Falling back to mock activities (document):", error);
      return mockActivities.filter(activity => activity.documentId === documentId);
    }
  }

  /**
   * Get activities by user
   */
  async getUserActivities(userName: string): Promise<Activity[]> {
    try {
      const response = await fetch(`/api/activities?user=${encodeURIComponent(userName)}&limit=100`);
      if (!response.ok) throw new Error(`Failed to fetch user activities: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn("Falling back to mock activities (user):", error);
      return mockActivities.filter(activity => activity.user === userName);
    }
  }

  /**
   * Add new activity
   */
  async addActivity(activity: Omit<Activity, "id" | "time">): Promise<Activity> {
    try {
      const response = await fetch('/api/activities', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(activity),
      });
      if (!response.ok) throw new Error(`Failed to add activity: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn("Falling back to mock activities (add):", error);
      const newActivity: Activity = {
        ...activity,
        id: Date.now().toString(),
        time: "nå",
      };

      mockActivities.unshift(newActivity);
      return newActivity;
    }
  }
}

// Export singleton instance
export const activityService = new ActivityService();
