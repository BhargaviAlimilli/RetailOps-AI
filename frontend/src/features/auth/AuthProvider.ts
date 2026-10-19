import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { logout } from '../../services/auth'
import {
  selectUser,
  sessionCleared,
  useAppDispatch,
  useAppSelector,
} from '../../store'

export function useAuth() {
  const user = useAppSelector(selectUser)
  const dispatch = useAppDispatch()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  return {
    user,
    async signOut() {
      try {
        await logout()
      } finally {
        dispatch(sessionCleared())
        queryClient.clear()
        navigate('/login', { replace: true })
      }
    },
  }
}
