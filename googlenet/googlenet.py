import os
import numpy as np
import tensorflow as tf
from os.path import isfile


class GoogleNet:
	def __init__(self, dropout, learning_rate, model_path, attributes, categories, img_dim):
		self.dropout = dropout
		self.learning_rate = learning_rate
		self.model_path = model_path

		self.attributes = attributes
		self.categories = categories

		self.img_dim = img_dim

		self.train_x = np.zeros((1, self.img_dim, self.img_dim, 3)).astype(np.float32)
		self.train_y = np.zeros((1, 1000))

		self.xdim = self.train_x.shape[1:]

		tf.set_random_seed(42)

		self.load_variables()
		self.define_placeholder_variables()
		self.construct_network()
		self.define_lr()

		self.define_loss()
		self.define_optimizer()
		self.define_accuracy()

		self.define_initialize_variables()

		self.define_session()
		self.run_init()
		self.define_saver()

	def load_variables(self):
		# download googlenet.npz from the geostyle webpage to load here
		if not isfile("models/googlenet.npz"):
			print("Error: download googlenet.npz from the geostyle webpage to load here and copy it to 'models' dir")
			exit()
		self.net_data = np.load(open("models/googlenet.npz", "rb"), encoding="latin1").item()


	def define_placeholder_variables(self):
		self.x = {}
		self.y = {}
		for i in range(len(self.attributes)):
			self.x[self.attributes[i]] = tf.placeholder(tf.float32, (None,) + self.xdim)
			self.y[self.attributes[i]] = tf.placeholder(tf.float32, (None, len(self.categories[i])))
		self.keep_prob = tf.placeholder(tf.float32) #dropout (keep probability)


	def _conv2d(self, inputs, filters, kernel_size, strides, name, trainable, reuse):
		padding = 'SAME'
		layer = tf.layers.conv2d(inputs=inputs, filters=filters, kernel_size=[kernel_size, kernel_size],\
			kernel_initializer=tf.constant_initializer(self.net_data[name]["weights"]),\
			bias_initializer=tf.constant_initializer(self.net_data[name]["biases"]),\
			padding=padding, strides=strides, name=name, use_bias=True, trainable=trainable, reuse=reuse)
		return layer


	def _conv2d_relu(self, inputs, filters, kernel_size, strides, name, trainable, reuse):
		return tf.nn.relu(self._conv2d(inputs, filters, kernel_size, strides, name, trainable, reuse))


	def _inception_module(self, name, input, trainable, filters, reuse):
		inception_1x1 = self._conv2d_relu(input, filters[0], 1, 1, name+'_1x1', trainable, reuse)
		inception_3x3_reduce = self._conv2d_relu(input, filters[1], 1, 1, name+'_3x3_reduce', trainable, reuse)
		inception_3x3 = self._conv2d_relu(inception_3x3_reduce, filters[2], 3, 1, name+'_3x3', trainable, reuse)
		inception_5x5_reduce = self._conv2d_relu(input, filters[3], 1, 1, name+'_5x5_reduce', trainable, reuse)
		inception_5x5 = self._conv2d_relu(inception_5x5_reduce, filters[4], 5, 1, name+'_5x5', trainable, reuse)
		inception_pool = tf.layers.max_pooling2d(inputs=input, pool_size=3, strides=1, padding='SAME')
		inception_pool_proj = self._conv2d_relu(inception_pool, filters[5], 1, 1, name+'_pool_proj', trainable, reuse)

		output = tf.concat([inception_1x1, inception_3x3, inception_5x5, inception_pool_proj], axis=-1, name="output_"+name)
		return output


	def construct_network(self):
		self.train_conv1 = True
		self.train_conv2 = True
		self.train_conv3 = True
		self.train_conv4 = True
		self.train_conv5 = True

		self.features = {}
		self.fc_out = {}
		self.prob = {}
		for i in range(len(self.attributes)):
			if i == 0:
				reuse = None
			else:
				reuse = True
			self.input = self.x[self.attributes[i]] - tf.constant([124.0, 117.0, 104.0])
			self.input = tf.reverse(self.input, axis=[3])

			self.conv1 = self._conv2d_relu(self.input, 64, 7, 2, "conv1_7x7_s2", self.train_conv1, reuse)
			self.pool1 = tf.layers.max_pooling2d(inputs=self.conv1, pool_size=3, strides=2, padding='SAME')
			self.lrn1 = tf.nn.lrn(self.pool1, depth_radius=2, bias=1, alpha=0.00002, beta=0.75)

			self.conv2_reduce = self._conv2d_relu(self.lrn1, 64, 1, 1, "conv2_3x3_reduce", self.train_conv2, reuse)
			self.conv2 = self._conv2d_relu(self.conv2_reduce, 192, 3, 1, "conv2_3x3", self.train_conv2, reuse)
			self.lrn2 = tf.nn.lrn(self.conv2, depth_radius=2, bias=1, alpha=0.00002, beta=0.75)
			self.pool2 = tf.layers.max_pooling2d(inputs=self.lrn2, pool_size=3, strides=2, padding='SAME')

			self.inception_3a = self._inception_module("inception_3a", self.pool2, self.train_conv3, [64, 96, 128, 16, 32, 32], reuse)
			self.inception_3b = self._inception_module("inception_3b", self.inception_3a, self.train_conv3, [128, 128, 192, 32, 96, 64], reuse)
			self.pool3 = tf.layers.max_pooling2d(inputs=self.inception_3b, pool_size=3, strides=2, padding='SAME')

			self.inception_4a = self._inception_module("inception_4a", self.pool3, self.train_conv4, [192, 96, 208, 16, 48, 64], reuse)
			self.inception_4b = self._inception_module("inception_4b", self.inception_4a, self.train_conv4, [160, 112, 224, 24, 64, 64], reuse)
			self.inception_4c = self._inception_module("inception_4c", self.inception_4b, self.train_conv4, [128, 128, 256, 24, 64, 64], reuse)
			self.inception_4d = self._inception_module("inception_4d", self.inception_4c, self.train_conv4, [112, 144, 288, 32, 64, 64], reuse)
			self.inception_4e = self._inception_module("inception_4e", self.inception_4d, self.train_conv4, [256, 160, 320, 32, 128, 128], reuse)
			self.pool4 = tf.layers.max_pooling2d(inputs=self.inception_4e, pool_size=3, strides=2, padding='SAME')

			self.inception_5a = self._inception_module("inception_5a", self.pool4, self.train_conv5, [256, 160, 320, 32, 128, 128], reuse)
			self.inception_5b = self._inception_module("inception_5b", self.inception_5a, self.train_conv5, [384, 192, 384, 48, 128, 128], reuse)
			self.pool5 = tf.nn.pool(self.inception_5b, [7, 7], "AVG", padding="VALID")

			self.features[self.attributes[i]] = tf.reshape(tf.nn.dropout(self.pool5, keep_prob=self.keep_prob), [-1, 1024])
			self.fc_out[self.attributes[i]] = tf.layers.dense(inputs=self.features[self.attributes[i]], units=len(self.categories[i]))
			self.prob[self.attributes[i]] = tf.nn.softmax(self.fc_out[self.attributes[i]])


	def define_initialize_variables(self):
		self.init = tf.initialize_all_variables()
	def define_session(self):
		config = tf.ConfigProto()
		# config.gpu_options.allow_growth = True
		self.session = tf.Session(config=config)

	#Saver for model
	def define_saver(self):
		self.saver = tf.train.Saver()
	def restore_model(self):
		self.saver.restore(self.session, self.model_path)
	def save_model(self):
		self.saver.save(self.session, self.model_path)

	def define_lr(self):
		self.global_step = tf.Variable(0, trainable=False)
		self.learning_rate = tf.train.exponential_decay(self.learning_rate, self.global_step, 1, 0.9999, staircase=True)

	def define_loss(self):
		# self.loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=self.fc_out, labels=self.y))
		self.loss = {}
		for i in range(len(self.attributes)):
			self.loss[self.attributes[i]] = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=self.fc_out[self.attributes[i]], labels=self.y[self.attributes[i]]))
			if i == 0:
				self.Loss = self.loss[self.attributes[i]]
			else:
				self.Loss += self.loss[self.attributes[i]]

	def define_optimizer(self):
		self.Optimizer = tf.train.MomentumOptimizer(learning_rate=self.learning_rate, momentum=0.9).minimize(self.Loss, global_step=self.global_step)

	def define_accuracy(self):
		# Evaluate model
		self.correct_pred = {}
		self.accuracy = {}
		for i in range(len(self.attributes)):
			self.correct_pred[self.attributes[i]] = tf.equal(tf.argmax(self.prob[self.attributes[i]], 1), tf.argmax(self.y[self.attributes[i]], 1))
			self.accuracy[self.attributes[i]] = tf.reduce_mean(tf.cast(self.correct_pred[self.attributes[i]], tf.float32))
		# self.correct_pred = tf.equal(tf.argmax(self.prob, 1), tf.argmax(self.y, 1))
		# self.accuracy = tf.reduce_mean(tf.cast(self.correct_pred, tf.float32))

	def run_init(self):
		self.session.run(self.init)

	def run_training(self, batch_xs, batch_ys):
		feed_dict = {}
		for i in range(len(self.attributes)):
			feed_dict[self.x[self.attributes[i]]] = batch_xs[i]
			feed_dict[self.y[self.attributes[i]]] = batch_ys[i]
		feed_dict[self.keep_prob] = self.dropout
		self.session.run(self.Optimizer, feed_dict=feed_dict)
	def get_lr(self):
		return self.session.run(self.learning_rate)
	def get_loss(self, batch_x, batch_y, attribute):
		return self.session.run(self.loss[attribute], feed_dict={self.x[attribute]: batch_x, self.y[attribute]: batch_y, self.keep_prob : 1})
	def get_accuracy(self, batch_x, batch_y, attribute):
		return self.session.run(self.accuracy[attribute], feed_dict={self.x[attribute]: batch_x, self.y[attribute]: batch_y, self.keep_prob : 1})
	def get_features(self, images):
		return self.session.run(self.features[self.attributes[0]], feed_dict={self.x[self.attributes[0]]:images, self.keep_prob : 1})
	def get_prob(self, batch_x, attribute):
		return self.session.run(self.prob[attribute], feed_dict={self.x[attribute]: batch_x, self.keep_prob : 1})
	def get_class(self, batch_x, attribute):
		prob = self.session.run(self.prob[attribute], feed_dict={self.x[attribute]: batch_x, self.keep_prob : 1})
		return np.argmax(prob, axis=1)
	def get_classes(self, batch_x):
		feed_dict = {self.keep_prob : 1}
		for attribute in self.attributes:
			feed_dict[self.x[attribute]] = batch_x
		probs = self.session.run([self.prob[attribute] for attribute in self.attributes], feed_dict=feed_dict)
		classes = [(np.expand_dims(np.argmax(prob, axis=1), axis=1))for prob in probs]
		return np.concatenate(classes, axis=1)
	def get_classprobs(self, batch_x):
		feed_dict = {self.keep_prob : 1}
		for attribute in self.attributes:
			feed_dict[self.x[attribute]] = batch_x
		probs = self.session.run([self.prob[attribute] for attribute in self.attributes], feed_dict=feed_dict)
		cat_probs = np.concatenate(probs, axis=1)
		return cat_probs
