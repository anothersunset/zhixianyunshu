import { defineStore } from "pinia"
import { http } from "@/api/client"

export interface UserInfo { id: number; username: string; role: string }

export const useUserStore = defineStore("user", {
  state: () => ({ info: null as UserInfo | null }),
  actions: {
    async loadMe() {
      this.info = (await http.get("/users/me")) as UserInfo
    },
    logout() {
      localStorage.removeItem("zq_token")
      this.info = null
    },
  },
})
