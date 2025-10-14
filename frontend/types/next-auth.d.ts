import NextAuth from "next-auth"

declare module "next-auth" {
  interface Session {
    accessToken?: string
    roles?: string[]
  }

  interface JWT {
    accessToken?: string
    refreshToken?: string
    expiresAt?: number
    roles?: string[]
  }
}

declare module "next-auth/providers/keycloak" {
  interface KeycloakProfile {
    realm_access?: {
      roles: string[]
    }
    [key: string]: any
  }
}