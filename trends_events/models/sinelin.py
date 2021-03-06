import numpy as np
from scipy.optimize import curve_fit
from numpy import sin

def linear(x, m, c):
	return m*x+c


def sinusoidal_lin(x,r,m1,f,o,b1,m2,b2):
	return r*(m1*(sin(f*x+o))+b1)+(1-r)*(m2*x+b2)


class SinusoidalLinear:
	def __init__(self):
		self.VLARGE = 5000
		self.explain_factor = 0.8
		self.sinlbounds = ([0,0, 1/72, -3.14, 0,-1/100,0], [1,1, 1/6, 3.14, 1,1/100,1])


	def predict(self, data, confs, gap=0, predtill=1):
		assert predtill-1 <= gap
		true = data[:, -predtill:, :]
		pred = []

		for i in range(data.shape[2]):
			trend = data[0, :-1-gap, i]
			conf = confs[0, :-1-gap, i]

			errs = []
			errf = self.VLARGE
			fits = []

			weeks = list(range(trend.shape[0]))
			try:
				params, _ = curve_fit(linear, range(len(weeks)), trend, method='lm', p0=(0, 0), sigma=conf)
				err_l = np.sqrt(np.sum(np.square(np.array([linear(tmp, params[0], params[1]) for tmp in range(len(weeks))])-trend)))
				errs.append(err_l)
				fits.append(params)
				if err_l < errf:
					errf = err_l
					pred_tmp = [linear(tmp, params[0], params[1]) for tmp in range(data.shape[1]-predtill, data.shape[1])]
			except KeyboardInterrupt:
				raise
			except:
				raise
			try:
				params, _ = curve_fit(sinusoidal_lin, range(len(weeks)), trend, method='trf', p0=(1, np.max(trend)-np.min(trend), 1/8, 0, (np.max(trend)+np.min(trend))/2, 0, 0), bounds=self.sinlbounds, sigma=conf)
				r, m1, f, o, b1, m2, b2 = params[0], params[1], params[2], params[3], params[4], params[5], params[6]
				err1 = np.sqrt(np.sum(np.square(np.array([sinusoidal_lin(tmp, r, m1, f, o, b1, m2, b2) for tmp in range(len(weeks))])-trend)))
				errs.append(err1)
				fits.append(params)
				if err1 < errf and err1 < self.explain_factor*err_l:
					pred_tmp = [sinusoidal_lin(tmp, r, m1, f, o, b1, m2, b2) for tmp in range(data.shape[1]-predtill, data.shape[1])]
			except KeyboardInterrupt:
				raise
			except:
				pass

			if i%100 == 0:
				print("Done", i, "/", data.shape[2])
			pred.append(pred_tmp)
		pred = np.expand_dims(np.array(pred).T, axis=0)
		mae = np.mean(np.abs(pred-true))
		mape = np.mean(np.abs(pred-true)/true)*100
		return mae, mape, pred
