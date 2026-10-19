import {
  configureStore,
  createSlice,
  type PayloadAction,
} from '@reduxjs/toolkit'
import { useDispatch, useSelector } from 'react-redux'
import type { AuthSession } from '../services/auth'

type AuthState = AuthSession | null
const authSlice = createSlice({
  name: 'auth',
  initialState: null as AuthState,
  reducers: {
    sessionEstablished: (_state, action: PayloadAction<AuthSession>) =>
      action.payload,
    sessionCleared: () => null,
  },
})
export const { sessionEstablished, sessionCleared } = authSlice.actions
export const store = configureStore({ reducer: { auth: authSlice.reducer } })
export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
export const useAppDispatch = useDispatch.withTypes<AppDispatch>()
export const useAppSelector = useSelector.withTypes<RootState>()
export const selectUser = (state: RootState) => state.auth?.user ?? null
export const getAccessToken = () => store.getState().auth?.access_token
