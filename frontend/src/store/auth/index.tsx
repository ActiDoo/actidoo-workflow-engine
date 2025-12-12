import reducer from '@/store/auth/reducer';
import * as actions from '@/store/auth/actions';
import saga from '@/store/auth/saga';

export default {
  reducer,
  action: actions,
  saga,
};
