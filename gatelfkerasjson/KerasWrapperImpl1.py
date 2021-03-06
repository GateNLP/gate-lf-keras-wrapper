from __future__ import division
import numpy as np

from keras.models import Sequential, Model, load_model
from keras.layers import Dense, Input, Concatenate,Reshape, Lambda, BatchNormalization
from keras.layers import LSTM, Conv1D, Flatten, Dropout, TimeDistributed, MaxPooling1D, Conv2D
from keras.layers.embeddings import Embedding
from keras.backend import tf as K
from keras.utils import to_categorical
import pickle
import tensorflow as tf
from keras.layers.core import *

#setattr(K.tf.contrib.rnn.GRUCell, '__deepcopy__', lambda self, _: self)
#setattr(K.tf.contrib.rnn.BasicLSTMCell, '__deepcopy__', lambda self, _: self)
#setattr(K.tf.contrib.rnn.MultiRNNCell, '__deepcopy__', lambda self, _: self)


def sequenceModelReshape(x, outputshape):
    resized = K.reshape(x, shape=outputshape)
    return resized

class KerasWrapperImpl1(object):
    def __init__(self, dataSet, configDict=None):
        assert isinstance(dataSet, object)
        self.ds = dataSet
        self.ds.target.set_as_onehot(True)

        self.inputMask = [None] * self.ds.nFeatures
        self.featureKindList = [None] * self.ds.nFeatures
        self.num_idxs = dataSet.get_float_feature_idxs()
        self.nom_idxs = dataSet.get_index_feature_idxs()
        self.ngr_idxs = dataSet.get_indexlist_feature_idxs()
        self.genMask()
        self.inputMask = np.array(self.inputMask)
        #print(self.inputMask)
        #print(self.featureKindList)
        self.featureKindList = np.array(self.featureKindList)
        self.uniqueAttri, self.AttriCount = np.unique(self.inputMask, return_counts=True)
        self.batchSize = 64
        self.embeddingSize = 16
        self.inputLayerList = []
        self.outputLayersList = []
        self.featureState = []
        self.model = None
        self.inputShape=[]
        self.finalOutputLayer=None

    def applyModel(self, singleInstance, converted=False):
        #print(singleInstance)
        singleInstance = self.ds.convert_indep(singleInstance)
        #print(singleInstance)
        if self.ds.isSequence:
            label_list = []
            conf_list = []
            numInputAttribute = len(self.uniqueAttri)
            full_input = []
            for each_time in singleInstance:
                inputX = []
                for featureid in range(len(each_time)):
                    inputX.append(each_time[featureid])
                #print(inputX)
                full_input.append(inputX)
            prediction = self.model.predict(np.array([full_input]))
            #print(prediction) 
            for npItem in prediction[0]:
                idx = int(np.where(npItem == max(npItem))[0])
                #print(idx)
                getlabel = self.ds.target.idx2label
                #print(getlabel)
                labels = getlabel(idx)
                #print(labels)
                confidence = npItem[idx]
                label_list.append(labels)
                conf_list.append(confidence)
            return label_list, conf_list

        else:
            numInputAttribute = len(self.uniqueAttri)
            inputX = [[] for i in range(numInputAttribute)]
            for eachAttribute in inputX:
                eachAttribute.append([])
            for featureid in range(len(singleInstance)):
                #print(len(singleInstance))
                #print(self.inputMask)
                #print(self.inputMask[featureid])
                #print(singleInstance[featureid])
                inputX[self.inputMask[featureid]][-1].append(singleInstance[featureid])
            #print(inputX)
            netInput = []
            for item in inputX:
                netInput.append(np.array(item))
            prediction = self.model.predict(netInput)
            #prediction = self.model.predict(np.array([singleInstance]))
            #print(prediction)
            npItem = prediction[0]
            #print(npItem)
            idx = int(np.where(npItem == max(npItem))[0])
            #print(idx)
            getlabel = self.ds.target.idx2label
            #print(getlabel)
            labels = getlabel(idx)
            #print(labels)
            confidence = npItem[idx]
            return labels, confidence


    def loadModelWeights(self, modelprefix):
        #self.model = load_model(modelprefix+'nn.model')
        #self.model.summary()
        self.genKerasModel()
        self.model.summary()
        self.model.load_weights(modelprefix+'nn.weights')


        with open(modelprefix+'classParameters.pkl', 'rb') as fp:
            self.featureKindList, self.inputMask, self.num_idxs, self.nom_idxs, self.ngr_idxs, self.uniqueAttri, self.AttriCount, self.featureState, self.inputShape = pickle.load(fp)

    def loadModel(self, modelprefix):
        self.model = load_model(modelprefix+'nn.model')
        #self.model.summary()
        with open(modelprefix+'classParameters.pkl', 'rb') as fp:
            self.featureKindList, self.inputMask, self.num_idxs, self.nom_idxs, self.ngr_idxs, self.uniqueAttri, self.AttriCount, self.featureState, self.inputShape = pickle.load(fp)


    def saveModelWeights(self, modelprefix):
        self.model.save_weights(modelprefix+'nn.weights')
        classParameters = [self.featureKindList, self.inputMask, self.num_idxs, self.nom_idxs, self.ngr_idxs, self.uniqueAttri, self.AttriCount, self.featureState, self.inputShape]
        with open(modelprefix+'classParameters.pkl','wb') as fp:
            pickle.dump(classParameters, fp)


    def saveModel(self, modelprefix):
        self.model.save(modelprefix+'nn.model')
        classParameters = [self.featureKindList, self.inputMask, self.num_idxs, self.nom_idxs, self.ngr_idxs, self.uniqueAttri, self.AttriCount, self.featureState, self.inputShape] 
        with open(modelprefix+'classParameters.pkl','wb') as fp:
            pickle.dump(classParameters, fp)

    def genMask(self):
        maskIdDict = {}
        maskIdx = -1
        if len(self.num_idxs) > 0:
            maskIdx += 1
            maskIdDict['A'] = maskIdx
            for idx in self.num_idxs:
                self.inputMask[idx] = maskIdx
                self.featureKindList[idx] = 'A'

        if len(self.nom_idxs) > 0:
            for idx in self.nom_idxs:
                currentFeature = self.ds.features.features[idx]
                currentFeatureKind = currentFeature.attrinfo['code']
                attriId = currentFeature.attrinfo['featureId']
                if attriId not in maskIdDict:
                    maskIdx += 1
                    self.inputMask[idx] = maskIdx
                    maskIdDict[attriId] = maskIdx
                else:
                    self.inputMask[idx] = maskIdDict[attriId]
                self.featureKindList[idx] = currentFeatureKind

        if len(self.ngr_idxs) > 0:
            for idx in self.ngr_idxs:
                currentFeature = self.ds.features.features[idx]
                currentFeatureKind = currentFeature.attrinfo['code']
                attriId = currentFeature.attrinfo['featureId']
                if attriId not in maskIdDict:
                    maskIdx += 1
                    self.inputMask[idx] = maskIdx
                    maskIdDict[attriId] = maskIdx
                else:
                    self.inputMask[idx] = maskIdDict[attriId]
                self.featureKindList[idx] = currentFeatureKind

    def genKerasModel(self):
        if self.ds.isSequence:
            self.genSequenceInputLayer()
            self.genSequenceHiddenLayer()
            if len(self.inputLayerList) > 1:
                allHidden = Concatenate()(self.outputLayersList)
            else:
                allHidden = self.outputLayersList[0]
            output = TimeDistributed(Dense(self.ds.nClasses, activation='softmax'))(allHidden)
            self.finalOutputLayer = output
            model = Model(self.inputLayerList, output)
            
            model.compile(loss='binary_crossentropy', optimizer='Adamax', metrics=['accuracy'])
            model.summary()
        else:
            self.genInputLayer()
            self.genHiddenLayers()
            print(len(self.outputLayersList))
            if len(self.inputLayerList) > 1:
                allHidden = Concatenate()(self.outputLayersList)
            else:
                allHidden = self.outputLayersList[0]
            if self.ds.nClasses > 2:
                output = Dense(self.ds.nClasses, activation="softmax")(allHidden)
            else:
                # leave it for testing
                output = Dense(self.ds.nClasses, activation="sigmoid")(allHidden)
                # output = Dense(1, activation="sigmoid")(allHidden)
            self.finalOutputLayer = output
            model = Model(self.inputLayerList, output)
            model.compile(loss='binary_crossentropy', optimizer='Adamax', metrics=['accuracy'])
            model.summary()
        print(self.inputLayerList)
        print(self.finalOutputLayer)
        testmodel = Model(self.inputLayerList, self.finalOutputLayer)
        testmodel.compile(loss='binary_crossentropy', optimizer='Adamax', metrics=['accuracy'])
        testmodel.summary()
        self.model = model


    def genSequenceHiddenLayer(self):
        for i in range(len(self.inputLayerList)):
            currentShape = self.inputShape[i]
            print(currentShape)
            current_output = self.outputLayersList[i]
            print(current_output)
            current_output = LSTM(units=16, return_sequences=True)(current_output)
            self.outputLayersList[i] = current_output

    def genSequenceInputLayer(self):
        print(self.uniqueAttri)
        sequenceFeature = False
        numFeature = False
        print(self.featureKindList)
        for attribId in self.uniqueAttri:
            featureIndexList = np.where(self.inputMask == attribId)
            currentKindList = self.featureKindList[featureIndexList]
            if (1):
                vocabSize = self.ds.features.features[featureIndexList[0][0]].vocab.size() + 10000
                current_input = Input(shape=(None,len(currentKindList)))
                print(current_input)
                current_output = Embedding(vocabSize, self.embeddingSize)(current_input)
                print(current_output)
                s = K.shape(current_output)
                print(s)
                outputShape = [-1, s[1],self.embeddingSize*len(currentKindList)]
                #current_output = Lambda(sequenceModelReshape, arguments={'outputshape':outputShape})(current_output)
                current_output = Reshape((-1, self.embeddingSize*len(currentKindList)))(current_output)
                print(current_output)
            self.inputLayerList.append(current_input)
            self.outputLayersList.append(current_output)
            self.featureState.append([sequenceFeature, numFeature])
            self.inputShape.append((None,None,len(currentKindList),self.embeddingSize))

    def genHiddenLayers(self):
        for i in range(len(self.inputLayerList)):
            sequenceFeature = self.featureState[i][0]
            numFeature = self.featureState[i][1]
            current_output = self.outputLayersList[i]
            print(current_output)
            if numFeature:
                current_output = Dense(32)(current_output)
            else:
                if sequenceFeature:
                    current_output = LSTM(units=16, return_sequences=False)(current_output)
                    current_output = Dense(32)(current_output)
                    #current_output = Conv1D(filters=32, kernel_size=2, strides=1, activation='relu')(current_output)

                else:
                    current_output = Conv1D(filters=32, kernel_size=2, strides=1, activation='relu')(current_output)
                # current_output = MaxPooling1D(pool_size=(2))(current_output)
                    current_output = Dropout(0.2)(current_output)
                    current_output = Flatten()(current_output)
                    current_output = Dense(32)(current_output)
            self.outputLayersList[i] = current_output

    def genInputLayer(self):
        # unique, counts = np.unique(self.inputMask, return_counts=True)
        print(self.uniqueAttri)
        sequenceFeature = False
        numFeature = False
        for attribId in self.uniqueAttri:
            featureIndexList = np.where(self.inputMask == attribId)
            currentKindList = self.featureKindList[featureIndexList]
            if ('L' in currentKindList):
                vocabSize = self.ds.features.features[featureIndexList[0][0]].vocab.size() + 10000
                current_input = Input(shape=(len(currentKindList),))
                current_output = Embedding(vocabSize, self.embeddingSize, input_length=len(currentKindList))(
                    current_input)
            elif ('N' in currentKindList):
                sequenceFeature = True
                vocabSize = self.ds.features.features[featureIndexList[0][0]].vocab.size() + 10000
                current_input = Input(shape=(None,))

                current_output = Embedding(vocabSize, self.embeddingSize)(current_input)
            elif ('A' in currentKindList):
                numFeature = True
                current_input = Input(shape=(len(currentKindList),))
                current_output = Dense(10)(current_input)
            else:
                print('unsupported feature type')
            self.inputLayerList.append(current_input)
            self.outputLayersList.append(current_output)
            self.featureState.append([sequenceFeature, numFeature])

    def trainModel(self, batchSize=64, nb_epoch=20):
        self.ds.split(convert=True, keep_orig=False, validation_part=0.05)
        valset = self.ds.validation_set_converted(as_batch=True)
        print(len(valset[0]))
        valx = self.convertX(valset[0])
        valy = valset[1]
        newvalx = []
        #print(valx)
        for item in valx:
            newvalx.append(np.array(item))

        for i in range(nb_epoch):
            print('epoch ', i)
            self.trainKerasModelBatch(batchSize)
            #print(newvalx[0].shape)
            #print(newvalx)
            valLoss = self.model.evaluate(x=newvalx, y=np.array(valy))
            print('valLoss', valLoss)

    def trainKerasModelBatch(self, batchSize):
        convertedTraining = self.ds.batches_converted(train=True, batch_size=batchSize)
        tl = []
        ta = []
        for batchInstances in convertedTraining:
            featureList = batchInstances[0]
            target = batchInstances[1]
            #print(len(target))
            #print(target)
            #print(self.ds.nClasses)
            miniBatchY = target
            #print(len(miniBatchY))
            #print(miniBatchY)
            miniBatchX = self.convertX(featureList)
            # print(miniBatchY)
            # print(miniBatchX)
            currentLoss, currentAccuracy = self.trainMiniBatch(miniBatchX, miniBatchY)
            #print(currentLoss,currentAccuracy)
            tl.append(currentLoss)
            ta.append(currentAccuracy)
        #print(tl)
        print('train loss')
        print(sum(tl)/len(tl), sum(ta)/len(ta))

    def convertX(self, xList):
        # numInputAttribute = max(self.inputMask)+1
        numInputAttribute = len(self.uniqueAttri)
        #print(numInputAttribute)
        miniBatchX = [[] for i in range(numInputAttribute)]
        #print(miniBatchX)
        #print(len(xList))
        #print(len(xList[0]))
        #print(len(xList[0][0]))



        for xid in range(len(xList[0])):
            #for eachAttribute in miniBatchX:
            #    eachAttribute.append([])
            if self.ds.isSequence and ('N' not in self.featureKindList):
                allTime = [[] for i in range(numInputAttribute)]
                for timeStamp in range(len(xList[0][0])):
                    eachTime = [[] for i in range(numInputAttribute)]
                    for maskIdx in range(len(self.inputMask)):
                        eachTime[self.inputMask[maskIdx]].append(xList[maskIdx][xid][timeStamp])
                    for ii in range(numInputAttribute):
                        allTime[ii].append(eachTime[ii])
                for iii in range(numInputAttribute):
                    miniBatchX[iii].append(allTime[iii])


            else:
                for eachAttribute in miniBatchX:
                    eachAttribute.append([])
                for maskIdx in range(len(self.inputMask)):
                    #print(xList[maskIdx][xid])
                    #print(maskIdx)
                    #print(self.inputMask[maskIdx])
                    #print(miniBatchX[self.inputMask[maskIdx]][-1])
                    if self.featureKindList[maskIdx] == 'N':# or self.ds.isSequence:
                        miniBatchX[self.inputMask[maskIdx]][-1]+=xList[maskIdx][xid]
                    else:
                        miniBatchX[self.inputMask[maskIdx]][-1].append(xList[maskIdx][xid])
            #print(miniBatchX)
            #break
        #print(miniBatchX[0])
        return miniBatchX

    def trainMiniBatch(self, miniBatchX, miniBatchY):
        # print('training')
        newX = []
        for item in miniBatchX:
            newX.append(np.array(item))
        #print(newX[0][0])
        #print(newX[0].shape)
        #print(len(miniBatchY))
        #print(newX[0],miniBatchY[0])
        #print(miniBatchY[0])
        trainLoss = self.model.train_on_batch(x=newX, y=np.array(miniBatchY))
        # loss = self.model.test_on_batch(x=newX, y=np.array(miniBatchY))
        # print(trainLoss)
        return trainLoss
