import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Navigate, Outlet } from 'react-router'
import { selectUser, useAppSelector } from '../../store'
export function RequireAuth() {
  const user = useAppSelector(selectUser)
  const queryClient = useQueryClient()
  useEffect(() => {
    if (!user) queryClient.clear()
  }, [user, queryClient])
  return user ? <Outlet /> : <Navigate to="/login" replace />
}
